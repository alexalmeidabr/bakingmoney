// Manual browser regression with synthetic data. No application database or TWS access.
// Run from the repository root using Node 22+ and Microsoft Edge (or BROWSER_PATH).
const {spawn}=require('node:child_process');
const {mkdtempSync,readFileSync,realpathSync,rmSync}=require('node:fs');
const {tmpdir}=require('node:os');
const {join}=require('node:path');
const http=require('node:http');
const assert=require('node:assert/strict');
async function main(){
 const calls=[], profile=mkdtempSync(join(tmpdir(),'baking-ui-edge-'));
 let sim=null, duplicate=null;
 const realTrigger={buy_trigger_price:90, reserve_enabled:false, reserve_percentage:0};
 const triggers=new Map();
 const other={id:3,name:'Account B scenario',additional_cash_usd:30};
 const getPlan=(name,trigger)=>{
   const baseline={symbol:'ABC',company_name:name,rating:'Buy',action:'Add',current_price:101,
     current_position_market_value:1010,current_position_weight:10.1,suggested_share_count:5,
     executable_action_amount:505,action_amount_label:'$505.00',funding_status:'Funded'};
   const manual={...baseline,current_price:103,manual_verified_price:103,current_position_market_value:1030,
     suggested_share_count:3,executable_action_amount:309,action_amount_label:'$309.00',
     recommended_action:'Add',manual_trigger_price:trigger?.buy_trigger_price,
     manual_trigger_status:trigger?'eligible':'no_manual_trigger',manual_price_source:'delayed ask'};
   return {linear_action_plan:[baseline],summary:{linear_summary:{}},manual_execution:{linear_action_plan:[manual],summary:{}}};
 };
 let hold=null, release=null, releaseCompleted=false;
 const server=http.createServer(async(req,res)=>{
  const u=new URL(req.url,'http://localhost'), path=u.pathname;
  if(path==='/outside'){
   res.setHeader('content-type','text/html');res.end('<!doctype html><p id="outside-page">Outside BakingMoney</p>');return;
  }
  if(path==='/' || path.startsWith('/static/')){
   const name=path==='/'?'static/index.html':path.slice(1);
   res.setHeader('content-type',path==='/'?'text/html':path.endsWith('.css')?'text/css':'text/javascript');
   res.end(readFileSync(name));return;
  }
  const chunks=[];for await(const c of req) chunks.push(c);
  const body=chunks.length?JSON.parse(Buffer.concat(chunks).toString()):{};
  calls.push([req.method,req.url,body]);
  let payload={};
  const account=u.searchParams.get('account_id');
  if(path==='/api/ib-accounts') payload={accounts:[{account_id:'A',display_name:'A',portfolio_data_available:true},{account_id:'B',display_name:'B',portfolio_data_available:true}]};
  if(path==='/api/action-plan-simulations'){
   if(req.method==='POST'){sim={id:1,...body};triggers.set(1,{...realTrigger});payload={simulation:sim};}
   else payload={simulations:account==='A'?[sim,duplicate].filter(Boolean):[other]};
  }
  const match=path.match(/^\/api\/action-plan-simulations\/(\d+)(.*)$/);
  if(match){
   const id=Number(match[1]), suffix=match[2];
   if(suffix==='/duplicate'){
    duplicate={...sim,id:2,name:'Independent duplicate'};
    triggers.set(2,{...triggers.get(id)});payload={simulation:duplicate};
   }else if(suffix==='' && req.method==='DELETE'){sim=null;triggers.delete(id);payload={deleted:true};}
   else if(suffix==='' && req.method==='PUT'){sim={...sim,...body};payload={simulation:sim};}
   else if(suffix==='/triggers/ABC'){
    if(req.method==='DELETE')triggers.delete(id);
    if(req.method==='PUT')triggers.set(id,body);
    payload={trigger:triggers.get(id)||null};
   }
  }
  if(path==='/api/manual-execution-triggers/ABC')payload={trigger:realTrigger};
  if(path.endsWith('/action-plan') || path.endsWith('/action-plan/ABC')){
   const id=match?Number(match[1]):null;
   const name=id===3?'ACCOUNT_B':id===2?'DUPLICATE':id===1?'ORIGINAL':'REAL';
   const plan=getPlan(name,id?triggers.get(id):realTrigger);
   payload=path.endsWith('/ABC')?{action_detail:plan.linear_action_plan[0], manual_execution_detail:plan.manual_execution.linear_action_plan[0]}:plan;
  }
  if(hold===path){
   hold=null;
   await new Promise(resolve=>{release=resolve});
   releaseCompleted=true;
  }
  res.setHeader('content-type','application/json');res.end(JSON.stringify(payload));
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const remote=Number(process.env.CDP_PORT || 19377);
 const edge=spawn(process.env.BROWSER_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless','--disable-gpu','--no-first-run','--disable-extensions','--remote-debugging-port='+remote,'--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
 let ws;
 try{
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 let tab;
 for(let i=0;i<100&&!tab;i++){try{const tabs=await(await fetch('http://127.0.0.1:'+remote+'/json')).json();tab=tabs.find(t=>t.type==='page'&&t.url==='about:blank')||tabs.find(t=>t.type==='page'&&!t.url.startsWith('edge://'));}catch{}if(!tab)await sleep(100);}
 if(!tab)throw Error('No Edge debugging tab');
 ws=new WebSocket(tab.webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r);
 let seq=0; const pending=new Map(),errors=[];
 ws.onmessage=e=>{const msg=JSON.parse(e.data);if(msg.id){const callback=pending.get(msg.id);if(callback)callback(msg);pending.delete(msg.id);}if(msg.method==='Runtime.exceptionThrown')errors.push(msg.params.exceptionDetails.exception?.description ||msg.params.exceptionDetails.text);};
 const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;const detail=method==='Runtime.evaluate'?' '+String(params.expression).slice(0,160):'';const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout: '+method+detail));},5000);pending.set(id,msg=>{clearTimeout(timer);resolve(msg);});ws.send(JSON.stringify({id,method,params}));});
 const run=async(expression)=>{const msg=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(msg.result?.exceptionDetails)throw Error(msg.result.exceptionDetails.exception?.description);return msg.result.result.value;};
 const until=async(exp)=>{for(let i=0;i<75;i++){if(await run(exp))return;await sleep(50);}throw Error('timeout '+exp+' '+JSON.stringify(errors)+' '+JSON.stringify(calls));};
 const baseUrl='http://127.0.0.1:'+server.address().port;
 await send('Runtime.enable');
 await send('Page.navigate',{url:baseUrl+'/outside'});
 await until("document.querySelector('#outside-page')?.textContent === 'Outside BakingMoney'");
 await send('Page.navigate',{url:baseUrl+'/'});
 await until("document.querySelector('#portfolio-account-select')?.options.length >= 2");
 const choose=async(selector,value)=>run(`{const el=document.querySelector(${JSON.stringify(selector)});el.value=${JSON.stringify(value)};el.dispatchEvent(new Event('change'));}`);
 const click=async(selector)=>run(`document.querySelector(${JSON.stringify(selector)}).click()`);
 const contains=(selector,text)=>until(`document.querySelector(${JSON.stringify(selector)})?.textContent.includes(${JSON.stringify(text)})`);
 const field='[data-trigger-field="buy_trigger_price"]';
 await choose('#portfolio-account-select','A');
 await run("document.querySelector('[data-view=action-plan-simulator]').click()");
 await until("document.querySelector('#simulation-status').textContent.includes('Create a simulation')");
 await run("document.querySelector('#simulation-new').click();document.querySelector('#simulation-name').value='Additional Investment';document.querySelector('#simulation-new-cash').value=20000;document.querySelector('#simulation-create').click()");
 await until("document.querySelector('#action-plan-status').textContent.includes('Loaded')");
 assert.equal(await run("document.querySelector('#simulation-settings').open"),false);
 assert.equal(await run("document.querySelector('#simulation-results #action-plan-workspace') !== null"),true);
 await run("document.querySelector('#simulation-settings').open=true;document.querySelector('#simulation-cash').value=30000;document.querySelector('#simulation-cash').dispatchEvent(new Event('input'));document.querySelector('#simulation-apply').click()");
 await until("document.querySelector('#simulation-summary').textContent.includes('30,000')");
 await until("document.querySelector('#simulation-results .linear-allocation-symbol')?.textContent === 'ABC'");
 const modeBefore=calls.length;
 await click('#action-plan-without-triggers');
 await contains('#simulation-results .action-amount-cell','$505.00');
 await click('#action-plan-with-triggers');
 await contains('#simulation-results .action-amount-cell','$309.00');
 assert.equal(calls.length,modeBefore,'mode changes must use cached rows');

 // Native history follows Action Plan -> Simulator -> action detail in both directions.
 await click('[data-view=action-plan]');
 await until("document.querySelector('#action-plan').classList.contains('active') && document.querySelector('#action-plan .linear-allocation-symbol')?.textContent === 'ABC'");
 const actionSequence=await run('history.state.sequence');
 await click('[data-view=action-plan-simulator]');
 await until("document.querySelector('#action-plan-simulator').classList.contains('active') && document.querySelector('#simulation-results .linear-allocation-symbol')?.textContent === 'ABC'");
 assert.equal(await run('history.state.sequence'),actionSequence+1);
 await click('#simulation-results .linear-allocation-symbol');
 await contains('#manual-trigger-detail','Simulation Triggers');
 await until(`document.querySelector('${field}')?.value === '90'`);
 const detailSequence=await run('history.state.sequence');
 await run('history.back()');
 await until("history.state.sequence === "+(detailSequence-1)+" && document.querySelector('#action-plan-detail-view').classList.contains('hidden')");
 await run('history.back()');
 await until("history.state.sequence === "+(detailSequence-2)+" && document.querySelector('#action-plan').classList.contains('active')");
 await run('history.forward()');
 await until("history.state.sequence === "+(detailSequence-1)+" && document.querySelector('#action-plan-simulator').classList.contains('active')");
 await run('history.forward()');
 await until("history.state.sequence === "+detailSequence+" && !document.querySelector('#action-plan-detail-view').classList.contains('hidden')");

 // Internal Back uses the same entry; active-sidebar selection and refresh add nothing.
 await click('#action-plan-detail-back-btn');
 await until("history.state.sequence === "+(detailSequence-1)+" && document.querySelector('#action-plan-detail-view').classList.contains('hidden')");
 const stableHistory=await run('({length:history.length,sequence:history.state.sequence})');
 await click('[data-view=action-plan-simulator]');
 await sleep(100);
 assert.deepEqual(await run('({length:history.length,sequence:history.state.sequence})'),stableHistory);
 await click('#simulation-refresh');
 await until("document.querySelector('#action-plan-status').textContent.includes('Loaded')");
 assert.deepEqual(await run('({length:history.length,sequence:history.state.sequence})'),stableHistory);

 // A rejected dirty Back is compensated without losing the edit; accepting later traverses once.
 await click('#simulation-results .linear-allocation-symbol');
 await until(`document.querySelector('${field}')?.value === '90'`);
 await run(`document.querySelector('${field}').value=111;document.querySelector('${field}').dispatchEvent(new Event('input'));window.confirm=()=>false;history.back()`);
 await until("history.state.screen.detail?.kind === 'action' && !document.querySelector('#action-plan-detail-view').classList.contains('hidden')");
 assert.equal(await run(`document.querySelector('${field}').value`),'111');
 await run('window.confirm=()=>true;history.back()');
 await until("history.state.screen.view === 'action-plan-simulator' && !history.state.screen.detail && document.querySelector('#action-plan-detail-view').classList.contains('hidden')");
 await run('history.forward()');
 await until(`history.state.screen.detail?.kind === 'action' && document.querySelector('${field}')?.value === '90'`);

 await run(`document.querySelector('${field}').value=110;document.querySelector('[data-trigger-field=reserve_enabled]').click();document.querySelector('[data-trigger-field=reserve_percentage]').value=60`);
 await click('[data-trigger-action=save]');
 await contains('[data-trigger-status]','Triggers saved.');
 assert.equal(triggers.get(1).buy_trigger_price,110);
 assert.equal(triggers.get(1).reserve_percentage,60);
 assert.equal(realTrigger.buy_trigger_price,90);
 await contains('#action-plan-detail-content','1,030');
 await click('[data-view=action-plan]');
 await until("document.querySelector('#action-plan .linear-allocation-symbol')?.textContent === 'ABC'");
 await click('#action-plan .linear-allocation-symbol');
 await contains('#manual-trigger-detail','Manual Execution Triggers');
 await until(`document.querySelector('${field}')?.value === '90'`);
 await click('[data-view=action-plan-simulator]');
 await until("document.querySelector('#simulation-results .linear-allocation-symbol')?.textContent === 'ABC'");
 await click('#simulation-results .linear-allocation-symbol');
 await until(`document.querySelector('${field}')?.value === '110'`);
 await click('#simulation-duplicate');
 await contains('#simulation-summary','Independent duplicate');
 await until("document.querySelector('#simulation-results .linear-allocation-symbol')?.textContent === 'ABC'");
 await click('#simulation-results .linear-allocation-symbol');
 await until(`document.querySelector('${field}')?.value === '110'`);
 await click('[data-trigger-action=clear]');
 await contains('[data-trigger-status]','Triggers cleared.');
 assert.equal(triggers.has(2),false);
 assert.equal(triggers.get(1).buy_trigger_price,110);
 await choose('#simulation-select','1');
 await until("document.querySelector('#simulation-results .linear-allocation-symbol')?.textContent === 'ABC'");
 hold='/api/action-plan-simulations/1/action-plan/ABC';
 await click('#simulation-results .linear-allocation-symbol');
 for(let i=0;i<100&&!release;i++)await sleep(20);
 assert.ok(release,'mock did not receive delayed detail request');
 await choose('#simulation-select','2');
 await contains('#simulation-summary','Independent duplicate');
 await until("document.querySelector('#simulation-results .linear-allocation-symbol')?.textContent === 'ABC'");
 await click('#simulation-results .linear-allocation-symbol');
 await contains('#action-plan-detail-content','DUPLICATE');
 release();release=null;await sleep(200);
 assert.ok(releaseCompleted);
 assert.equal(await run("document.querySelector('#action-plan-detail-content').textContent.includes('ORIGINAL')"),false);
 assert.equal(await run(`document.querySelector('${field}').value`),'');
 await choose('#simulation-select','1');
 await until("document.querySelector('#simulation-results .linear-allocation-symbol')?.textContent === 'ABC'");
 hold='/api/action-plan-simulations/1/action-plan';releaseCompleted=false;
 await click('#simulation-refresh');
 for(let i=0;i<100&&!release;i++)await sleep(20);
 assert.ok(release,'no delayed plan request');
 await choose('#portfolio-account-select','B');
 await contains('#simulation-summary','Account B scenario');
 await until("document.querySelector('#simulation-results .linear-allocation-symbol')?.textContent === 'ABC'");
 release();release=null;await sleep(200);
 assert.ok(releaseCompleted);
 assert.equal(await run("document.querySelector('#simulation-select').options.length"),1);
 await click('#simulation-results .linear-allocation-symbol');
 await contains('#action-plan-detail-content','ACCOUNT_B');
 await choose('#portfolio-account-select','A');
 await contains('#simulation-summary','Additional Investment');
 await until("document.querySelector('#simulation-results .linear-allocation-symbol')?.textContent === 'ABC'");
 await run("window.confirm=()=>true");
 await click('#simulation-delete');
 await contains('#simulation-summary','Independent duplicate');
 assert.equal(await run("document.querySelector('#simulation-select').options.length"),1);
 assert.equal(triggers.get(1),undefined);
 assert.equal(duplicate.name,'Independent duplicate');
 assert.equal(calls.filter(c=>c[1].includes('/api/manual-execution-triggers/') && c[0]!=='GET').length,0);
 for(const [method,url] of calls.filter(c=>c[1].includes('/api/action-plan')||c[1].includes('/api/manual-execution-triggers'))){
  const account=new URL(url,'http://local').searchParams.get('account_id');
  assert.ok(['A','B'].includes(account),method+' '+url);
  if(url.includes('/3/'))assert.equal(account,'B');
  if(/\/[12]\//.test(url))assert.equal(account,'A');
 }
 for(const [method,id] of [['PUT',1],['DELETE',2]]){
  const writes=calls.filter(c=>c[0]===method&&c[1].includes('/'+id+'/triggers/ABC'));assert.equal(writes.length,1);
  const i=calls.indexOf(writes[0]);assert.ok(calls[i+1][1].startsWith('/api/action-plan-simulations/'+id+'/action-plan?execution_modes=both'));
 }

 // Sequence zero remains the first app entry; one more Back reaches the earlier page.
 await run('history.go(-history.state.sequence)');
 await until("history.state?.sequence === 0 && document.querySelector('#analysis').classList.contains('active')");
 await run('history.back()');
 await until("location.pathname === '/outside' && document.querySelector('#outside-page')");
 await run('history.forward()');
 await until("location.pathname === '/' && history.state?.sequence === 0 && document.querySelector('#analysis').classList.contains('active')");
 assert.equal(errors.length,0,JSON.stringify(errors));
 console.log('Browser checks passed: native Back/Forward; internal Back; duplicate suppression; refresh stability; dirty-navigation rejection and acceptance; outside-site Back; cash creation/apply; cached modes; scoped trigger save and recalculation; real trigger unchanged; saved trigger re-open; independent duplicate and clear/recalculation; delayed detail after simulation switch; delayed plan after account switch; deletion selects surviving duplicate. No browser exceptions or real trigger writes.');
 console.log('Observed scoped requests:',calls.filter(c=>c[1].includes('/api/action-plan')||c[1].includes('/api/manual-execution-triggers')).length);
 }finally{
  if(ws){ws.send(JSON.stringify({id:9999,method:'Browser.close'}));ws.close();}
  edge.kill();server.closeAllConnections();server.close();
  await new Promise(resolve=>setTimeout(resolve,1000));
  const absoluteProfile=realpathSync(profile), absoluteTemp=realpathSync(tmpdir());
  if(absoluteProfile.startsWith(join(absoluteTemp,'baking-ui-edge-'))){
   rmSync(absoluteProfile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
  }
 }
}
main().then(()=>process.exit(0),e=>{console.error(e);process.exit(1)});
