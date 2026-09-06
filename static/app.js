const menuItems = document.querySelectorAll('.menu-item');
const views = document.querySelectorAll('.view');

const positionsStatusEl = document.getElementById('status');
const positionsTable = document.getElementById('positions-table');
const positionsTableBody = positionsTable.querySelector('tbody');
const positionsPortfolioSummaryEl = document.getElementById('positions-portfolio-summary');
const positionsPortfolioSummaryWarningEl = document.getElementById('positions-portfolio-summary-warning');
const refreshBtn = document.getElementById('refresh-btn');
const positionSortHeaders = document.querySelectorAll('#positions-table th.sortable');
const positionsRatingFilterEl = document.getElementById('positions-rating-filter');
const positionsRatingFilterToggleEl = document.getElementById('positions-rating-filter-toggle');
const positionsRatingFilterLabelEl = document.getElementById('positions-rating-filter-label');
const positionsRatingFilterPanelEl = document.getElementById('positions-rating-filter-panel');
const positionsRatingFilterSelectAllEl = document.getElementById('positions-rating-filter-select-all');
const positionsRatingFilterClearEl = document.getElementById('positions-rating-filter-clear');

const analysisStatusEl = document.getElementById('analysis-status');
const analysisTable = document.getElementById('analysis-table');
const analysisTableBody = analysisTable.querySelector('tbody');
const analysisSortHeaders = document.querySelectorAll('#analysis-table th.sortable');
const analysisSelectAllEl = document.getElementById('analysis-select-all');
const analysisSymbolInput = document.getElementById('analysis-symbol-input');
const analysisPortfolioFilterEl = document.getElementById('analysis-portfolio-filter');
const analysisRatingFilterEl = document.getElementById('analysis-rating-filter');
const analysisRatingFilterToggleEl = document.getElementById('analysis-rating-filter-toggle');
const analysisRatingFilterLabelEl = document.getElementById('analysis-rating-filter-label');
const analysisRatingFilterPanelEl = document.getElementById('analysis-rating-filter-panel');
const analysisRatingFilterSelectAllEl = document.getElementById('analysis-rating-filter-select-all');
const analysisRatingFilterClearEl = document.getElementById('analysis-rating-filter-clear');
const analysisAddBtn = document.getElementById('analysis-add-btn');
const analysisImportBtn = document.getElementById('analysis-import-btn');
const analysisRefreshPricesBtn = document.getElementById('analysis-refresh-prices-btn');
const analysisUpdateMomentumBtn = document.getElementById('analysis-update-momentum-btn');
const actionPlanStatusEl = document.getElementById('action-plan-status');
const actionPlanSummaryEl = document.getElementById('action-plan-summary');
const actionPlanLinearActionsPanelEl = document.getElementById('action-plan-linear-actions-panel');
const actionPlanLinearActionsTableBody = document.querySelector('#action-plan-linear-actions-table tbody');
const actionPlanLinearDetailTableBody = null;
const actionPlanLinearSortHeaders = document.querySelectorAll('#action-plan-linear-actions-table th.sortable');
const actionPlanRefreshBtn = document.getElementById('action-plan-refresh-btn');
const actionPlanListViewEl = document.getElementById('action-plan-list-view');
const actionPlanDetailViewEl = document.getElementById('action-plan-detail-view');
const actionPlanDetailBackBtn = document.getElementById('action-plan-detail-back-btn');
const actionPlanOpenAnalysisBtn = document.getElementById('action-plan-open-analysis-btn');
const actionPlanDetailTitleEl = document.getElementById('action-plan-detail-title');
const actionPlanDetailStatusEl = document.getElementById('action-plan-detail-status');
const actionPlanDetailContentEl = document.getElementById('action-plan-detail-content');
const linearCapExplanationModalEl = document.getElementById('linear-cap-explanation-modal');
const linearCapExplanationContentEl = document.getElementById('linear-cap-explanation-content');
const linearCapExplanationCloseBtn = document.getElementById('linear-cap-explanation-close-btn');
const actionPlanRatingFilterEl = document.getElementById('action-plan-rating-filter');
const actionPlanRatingFilterToggleEl = document.getElementById('action-plan-rating-filter-toggle');
const actionPlanRatingFilterLabelEl = document.getElementById('action-plan-rating-filter-label');
const actionPlanRatingFilterPanelEl = document.getElementById('action-plan-rating-filter-panel');
const actionPlanRatingFilterSelectAllEl = document.getElementById('action-plan-rating-filter-select-all');
const actionPlanRatingFilterClearEl = document.getElementById('action-plan-rating-filter-clear');
const actionPlanActionFilterEl = document.getElementById('action-plan-action-filter');
const actionPlanActionFilterToggleEl = document.getElementById('action-plan-action-filter-toggle');
const actionPlanActionFilterLabelEl = document.getElementById('action-plan-action-filter-label');
const actionPlanActionFilterPanelEl = document.getElementById('action-plan-action-filter-panel');
const actionPlanActionFilterSelectAllEl = document.getElementById('action-plan-action-filter-select-all');
const actionPlanActionFilterClearEl = document.getElementById('action-plan-action-filter-clear');
const analysisRerunSelectedBtn = document.getElementById('analysis-rerun-selected-btn');
const analysisCheckEventsBtn = document.getElementById('analysis-check-events-btn');

const analysisListView = document.getElementById('analysis-list-view');
const analysisDetailView = document.getElementById('analysis-detail-view');
const analysisBackBtn = document.getElementById('analysis-back-btn');
const analysisDetailTitle = document.getElementById('analysis-detail-title');
const analysisDetailStatus = document.getElementById('analysis-detail-status');
const analysisSummary = document.getElementById('analysis-summary');
const analysisScenariosBody = document.querySelector('#analysis-scenarios-table tbody');
const analysisAddExternalScenarioBtn = document.getElementById('analysis-add-external-scenario-btn');
const analysisScenarioOverlayTabsEl = document.getElementById('analysis-scenario-overlay-tabs');
const analysisScenarioOverlayTabButtons = document.querySelectorAll('.scenario-overlay-tab');
const analysisFinalScenarioPanelEl = document.getElementById('analysis-final-scenario-panel');
const analysisBakingMoneyScenarioPanelEl = document.getElementById('analysis-bakingmoney-scenario-panel');
const analysisExternalScenariosPanelEl = document.getElementById('analysis-external-scenarios-panel');
const analysisExternalScenarioModalEl = document.getElementById('analysis-external-scenario-modal');
const analysisExternalScenarioModalTitleEl = document.getElementById('analysis-external-scenario-modal-title');
const analysisExternalScenarioTitleEl = document.getElementById('analysis-external-scenario-title');
const analysisExternalScenarioWeightEl = document.getElementById('analysis-external-scenario-weight');
const analysisExternalScenarioNotesEl = document.getElementById('analysis-external-scenario-notes');
const analysisExternalScenarioJsonEl = document.getElementById('analysis-external-scenario-json');
const analysisExternalScenarioStatusEl = document.getElementById('analysis-external-scenario-status');
const analysisExternalScenarioSaveBtn = document.getElementById('analysis-external-scenario-save-btn');
const analysisExternalScenarioTemplateBtn = document.getElementById('analysis-external-scenario-template-btn');
const analysisExternalScenarioCancelBtn = document.getElementById('analysis-external-scenario-cancel-btn');
const analysisExternalScenarioCancelFormBtn = document.getElementById('analysis-external-scenario-cancel-form-btn');
const analysisVariablesBody = document.querySelector('#analysis-variables-table tbody');
const analysisVariableTabButtons = document.querySelectorAll('.analysis-variable-tab');
const analysisVariablesEmptyEl = document.getElementById('analysis-variables-empty');
const analysisVersionBar = document.getElementById('analysis-version-bar');
const analysisVersionMeta = document.getElementById('analysis-version-meta');
const analysisVersionPrevBtn = document.getElementById('analysis-version-prev-btn');
const analysisVersionNextBtn = document.getElementById('analysis-version-next-btn');
const analysisVersionSelect = document.getElementById('analysis-version-select');
const analysisEditVariablesBtn = document.getElementById('analysis-edit-variables-btn');
const analysisCopyKeyVarsBtn = document.getElementById('analysis-copy-key-vars-btn');
const analysisCopyReviewPromptBtn = document.getElementById('analysis-copy-review-prompt-btn');
const analysisImportVariablesBtn = document.getElementById('analysis-import-variables-btn');
const analysisKeyVariableImportModalEl = document.getElementById('analysis-key-variable-import-modal');
const analysisKeyVariableImportJsonEl = document.getElementById('analysis-key-variable-import-json');
const analysisKeyVariableImportStatusEl = document.getElementById('analysis-key-variable-import-status');
const analysisKeyVariableImportTemplateBtn = document.getElementById('analysis-key-variable-import-template-btn');
const analysisKeyVariableImportSaveBtn = document.getElementById('analysis-key-variable-import-save-btn');
const analysisKeyVariableImportCloseBtn = document.getElementById('analysis-key-variable-import-close-btn');
const analysisKeyVariableImportCancelBtn = document.getElementById('analysis-key-variable-import-cancel-btn');
const analysisAddVariableBtn = document.getElementById('analysis-add-variable-btn');
const analysisSaveVariablesBtn = document.getElementById('analysis-save-variables-btn');
const analysisCancelVariablesBtn = document.getElementById('analysis-cancel-variables-btn');
const analysisRerunBtn = document.getElementById('analysis-rerun-btn');
const analysisScenarioInfoBtn = document.getElementById('analysis-scenario-info-btn');
const analysisScenarioInfoModal = document.getElementById('analysis-scenario-info-modal');
const analysisScenarioInfoText = document.getElementById('analysis-scenario-info-text');
const analysisScenarioInfoCloseBtn = document.getElementById('analysis-scenario-info-close-btn');

const promptStatusEl = document.getElementById('prompt-status');
const promptBusinessModelEl = document.getElementById('prompt-business-model');
const promptKeyVariablesEl = document.getElementById('prompt-key-variables');
const promptScenariosEl = document.getElementById('prompt-scenarios');
const promptRecentEventCandidatesEl = document.getElementById('prompt-recent-event-candidates');
const promptRecentEventsEl = document.getElementById('prompt-recent-events');
const promptEarningsWatchpointsEl = document.getElementById('prompt-earnings-watchpoints');
const promptEarningsWatchpointAnalysisEl = document.getElementById('prompt-earnings-watchpoint-analysis');
const promptSaveBtn = document.getElementById('prompt-save-btn');
const promptResetBtn = document.getElementById('prompt-reset-btn');
const promptPreviewSymbolInput = document.getElementById('prompt-preview-symbol-input');
const promptPreviewBtn = document.getElementById('prompt-preview-btn');
const promptPreviewOutput = document.getElementById('prompt-preview-output');

const alertsStatusEl = document.getElementById('alerts-status');
const alertsTable = document.getElementById('alerts-table');
const alertsTableBody = alertsTable.querySelector('tbody');
const alertsStatusFilterEl = document.getElementById('alerts-status-filter');
const alertsListView = document.getElementById('alerts-list-view');
const alertDetailView = document.getElementById('alert-detail-view');
const alertDetailBackBtn = document.getElementById('alert-detail-back-btn');
const alertDetailTitleEl = document.getElementById('alert-detail-title');
const alertDetailStatusEl = document.getElementById('alert-detail-status');
const alertDetailPanelsEl = document.getElementById('alert-detail-panels');
const alertDetailTypeEl = document.getElementById('alert-detail-type');
const alertDetailAffectedEl = document.getElementById('alert-detail-affected');
const alertDetailEventEl = document.getElementById('alert-detail-event');
const alertDetailDateEl = document.getElementById('alert-detail-date');
const alertDetailSourcesEl = document.getElementById('alert-detail-sources');
const alertDetailSuggestedEl = document.getElementById('alert-detail-suggested');
const alertDetailReviewBtn = document.getElementById('alert-detail-review-btn');
const alertDetailDismissBtn = document.getElementById('alert-detail-dismiss-btn');
const alertDetailPrevBtn = document.getElementById('alert-detail-prev-btn');
const alertDetailNextBtn = document.getElementById('alert-detail-next-btn');
const alertDetailKeyvarsStatusEl = document.getElementById('alert-detail-keyvars-status');
const alertDetailVarsBody = document.querySelector('#alert-detail-vars-table tbody');
const alertDetailOpenAnalysisBtn = document.getElementById('alert-detail-open-analysis-btn');
const alertDetailEditVarsBtn = document.getElementById('alert-detail-edit-vars-btn');
const alertDetailAddVarBtn = document.getElementById('alert-detail-add-var-btn');
const alertDetailSaveVarsBtn = document.getElementById('alert-detail-save-vars-btn');
const alertDetailCancelVarsBtn = document.getElementById('alert-detail-cancel-vars-btn');
const alertDetailRerunBtn = document.getElementById('alert-detail-rerun-btn');

const configurationStatusEl = document.getElementById('configuration-status');
const configIbPriceWaitSecondsEl = document.getElementById('config-ib-price-wait-seconds');
const configIbDelayedPriceExtraWaitSecondsEl = document.getElementById('config-ib-delayed-price-extra-wait-seconds');
const configScenarioMultiPassEnabledEl = document.getElementById('config-scenario-multi-pass-enabled');
const configScenarioPassCountEl = document.getElementById('config-scenario-pass-count');
const configScenarioProbabilitySourceModeEl = document.getElementById('config-scenario-probability-source-mode');
const configScenarioProbabilityHybridAiWeightEl = document.getElementById('config-scenario-probability-hybrid-ai-weight');
const configScenarioProbabilityHybridBackendWeightEl = document.getElementById('config-scenario-probability-hybrid-backend-weight');
const configScenarioProbabilityBackendBaseMaxEl = document.getElementById('config-scenario-probability-backend-base-max');
const configScenarioProbabilityBackendBaseMinEl = document.getElementById('config-scenario-probability-backend-base-min');
const configActionPlanInputs = document.querySelectorAll('[data-action-plan-setting]');
const configActionPlanTotalEl = document.getElementById('config-action-plan-total');
const configHelpModalEl = document.getElementById('config-help-modal');
const configHelpTitleEl = document.getElementById('config-help-title');
const configHelpContentEl = document.getElementById('config-help-content');
const configHelpCloseBtn = document.getElementById('config-help-close-btn');
const configSaveBtn = document.getElementById('config-save-btn');
const configCancelBtn = document.getElementById('config-cancel-btn');
const configRestoreDefaultsBtn = document.getElementById('config-restore-defaults-btn');
const configRatingMinConvictionHoldThresholdEl = document.getElementById('config-rating-min-conviction-hold-threshold');
const configRatingStrongBuyMinUpsideEl = document.getElementById('config-rating-strong-buy-min-upside');
const configRatingStrongBuyMinDiffEl = document.getElementById('config-rating-strong-buy-min-diff');
const configRatingStrongBuyMinBullishConfidenceEl = document.getElementById('config-rating-strong-buy-min-bullish-confidence');
const configRatingBuyMinUpsideEl = document.getElementById('config-rating-buy-min-upside');
const configRatingBuyMinDiffEl = document.getElementById('config-rating-buy-min-diff');
const configRatingBuyMinBullishConfidenceEl = document.getElementById('config-rating-buy-min-bullish-confidence');
const configRatingSpeculativeBuyMinUpsideEl = document.getElementById('config-rating-speculative-buy-min-upside');
const configRatingSpeculativeBuyMinDiffEl = document.getElementById('config-rating-speculative-buy-min-diff');
const configRatingSpeculativeBuyMinBullishConfidenceEl = document.getElementById('config-rating-speculative-buy-min-bullish-confidence');
const configRatingSpeculativeBuyMinCoreDiffFloorEl = document.getElementById('config-rating-speculative-buy-min-core-diff-floor');
const configRatingStrongSellMaxUpsideEl = document.getElementById('config-rating-strong-sell-max-upside');
const configRatingStrongSellMaxDiffEl = document.getElementById('config-rating-strong-sell-max-diff');
const configRatingStrongSellMinBearishConfidenceEl = document.getElementById('config-rating-strong-sell-min-bearish-confidence');
const configRatingSellMaxUpsideEl = document.getElementById('config-rating-sell-max-upside');
const configRatingSellMaxDiffEl = document.getElementById('config-rating-sell-max-diff');
const configRatingSellMinBearishConfidenceEl = document.getElementById('config-rating-sell-min-bearish-confidence');
const twsDataToggleEl = document.getElementById('tws-data-toggle');
const twsDataStatusEl = document.getElementById('tws-data-status');
const backupStatusEl = document.getElementById('backup-status');
const backupExportBtn = document.getElementById('backup-export-btn');
const backupIncludeEnvEl = document.getElementById('backup-include-env');
const backupImportFileEl = document.getElementById('backup-import-file');
const backupRestoreEnvEl = document.getElementById('backup-restore-env');
const backupImportBtn = document.getElementById('backup-import-btn');
const earningsReviewStatusEl = document.getElementById('earnings-review-status');
const earningsReviewTableBody = document.querySelector('#earnings-review-table tbody');
const earningsReviewDetailTitleEl = document.getElementById('earnings-review-detail-title');
const earningsReviewDetailHeaderEl = document.getElementById('earnings-review-detail-header');
const earningsReviewDetailMetaEl = document.getElementById('earnings-review-detail-meta');
const earningsReviewGenerateBtn = document.getElementById('earnings-review-generate-btn');
const earningsReviewAnalyseBtn = document.getElementById('earnings-review-analyse-btn');
const earningsReviewKeyVariablesBody = document.querySelector('#earnings-review-key-variables-table tbody');
const earningsReviewWatchpointsEl = document.getElementById('earnings-review-watchpoints');
const earningsReviewListView = document.getElementById('earnings-review-list-view');
const earningsReviewSymbolView = document.getElementById('earnings-review-symbol-view');
const earningsReviewDetailView = document.getElementById('earnings-review-detail-view');
const earningsReviewBackBtn = document.getElementById('earnings-review-back-btn');
const earningsReviewAddSymbolEl = document.getElementById('earnings-review-add-symbol');
const earningsReviewAddBtn = document.getElementById('earnings-review-add-btn');
const earningsReviewSymbolBackBtn = document.getElementById('earnings-review-symbol-back-btn');
const earningsReviewSymbolTitleEl = document.getElementById('earnings-review-symbol-title');
const earningsReviewSymbolHeaderEl = document.getElementById('earnings-review-symbol-header');
const earningsReviewSymbolStatusEl = document.getElementById('earnings-review-symbol-status');
const earningsReviewSymbolTableBody = document.querySelector('#earnings-review-symbol-table tbody');
const earningsReviewCreateBtn = document.getElementById('earnings-review-create-btn');
const earningsReviewCreateForm = document.getElementById('earnings-review-create-form');
const earningsReviewCreateYearEl = document.getElementById('earnings-review-create-year');
const earningsReviewCreateQuarterEl = document.getElementById('earnings-review-create-quarter');
const earningsReviewCreateReleaseDateEl = document.getElementById('earnings-review-create-release-date');
const earningsReviewCreateSubmitBtn = document.getElementById('earnings-review-create-submit-btn');
const earningsReviewCreateCancelBtn = document.getElementById('earnings-review-create-cancel-btn');
const earningsReviewSnapshotSummaryEl = document.getElementById('earnings-review-snapshot-summary');
const earningsReviewDocumentTypeEl = document.getElementById('earnings-review-document-type');
const earningsReviewDocumentFileEl = document.getElementById('earnings-review-document-file');
const earningsReviewDocumentChooseBtn = document.getElementById('earnings-review-document-choose-btn');
const earningsReviewDocumentFileNameEl = document.getElementById('earnings-review-document-file-name');
const earningsReviewDocumentUploadBtn = document.getElementById('earnings-review-document-upload-btn');
const earningsReviewDocumentsStatusEl = document.getElementById('earnings-review-documents-status');
const earningsReviewDocumentsTableBody = document.querySelector('#earnings-review-documents-table tbody');
const earningsReviewTabWorkflowBtn = document.getElementById('earnings-review-tab-workflow');
const earningsReviewTabCalendarBtn = document.getElementById('earnings-review-tab-calendar');
const earningsReviewWorkflowPanelEl = document.getElementById('earnings-review-workflow-panel');
const earningsReviewCalendarPanelEl = document.getElementById('earnings-review-calendar-panel');
const earningsCalendarStatusEl = document.getElementById('earnings-calendar-status');
const earningsCalendarTableBody = document.querySelector('#earnings-calendar-table tbody');
const earningsCalendarPortfolioFilterEl = document.getElementById('earnings-calendar-portfolio-filter');
const earningsCalendarDateFilterEl = document.getElementById('earnings-calendar-date-filter');
const earningsCalendarDateFilterToggleEl = document.getElementById('earnings-calendar-date-filter-toggle');
const earningsCalendarDateFilterLabelEl = document.getElementById('earnings-calendar-date-filter-label');
const earningsCalendarDateFilterPanelEl = document.getElementById('earnings-calendar-date-filter-panel');
const earningsCalendarDateFilterSelectAllEl = document.getElementById('earnings-calendar-date-filter-select-all');
const earningsCalendarDateFilterClearEl = document.getElementById('earnings-calendar-date-filter-clear');
const earningsCalendarFiscalYearFilterEl = document.getElementById('earnings-calendar-fiscal-year-filter');
const earningsCalendarFiscalYearFilterToggleEl = document.getElementById('earnings-calendar-fiscal-year-filter-toggle');
const earningsCalendarFiscalYearFilterLabelEl = document.getElementById('earnings-calendar-fiscal-year-filter-label');
const earningsCalendarFiscalYearFilterPanelEl = document.getElementById('earnings-calendar-fiscal-year-filter-panel');
const earningsCalendarFiscalYearFilterOptionsEl = document.getElementById('earnings-calendar-fiscal-year-filter-options');
const earningsCalendarFiscalYearFilterSelectAllEl = document.getElementById('earnings-calendar-fiscal-year-filter-select-all');
const earningsCalendarFiscalYearFilterClearEl = document.getElementById('earnings-calendar-fiscal-year-filter-clear');
const earningsCalendarFiscalQuarterFilterEl = document.getElementById('earnings-calendar-fiscal-quarter-filter');
const earningsCalendarFiscalQuarterFilterToggleEl = document.getElementById('earnings-calendar-fiscal-quarter-filter-toggle');
const earningsCalendarFiscalQuarterFilterLabelEl = document.getElementById('earnings-calendar-fiscal-quarter-filter-label');
const earningsCalendarFiscalQuarterFilterPanelEl = document.getElementById('earnings-calendar-fiscal-quarter-filter-panel');
const earningsCalendarFiscalQuarterFilterSelectAllEl = document.getElementById('earnings-calendar-fiscal-quarter-filter-select-all');
const earningsCalendarFiscalQuarterFilterClearEl = document.getElementById('earnings-calendar-fiscal-quarter-filter-clear');
const earningsCalendarAddSymbolEl = document.getElementById('earnings-calendar-add-symbol');
const earningsCalendarAddFiscalYearEl = document.getElementById('earnings-calendar-add-fiscal-year');
const earningsCalendarAddFiscalQuarterEl = document.getElementById('earnings-calendar-add-fiscal-quarter');
const earningsCalendarAddReleaseDateEl = document.getElementById('earnings-calendar-add-release-date');
const earningsCalendarAddReleaseTimingEl = document.getElementById('earnings-calendar-add-release-timing');
const earningsCalendarAddBtn = document.getElementById('earnings-calendar-add-btn');
const earningsCalendarReleaseDateHeaderEl = document.getElementById('earnings-calendar-release-date-header');

let latestPositions = [];
let positionSort = { key: 'marketValue', direction: 'desc' };
let latestAnalysis = [];
let latestActionPlanPayload = { action_plan: [], summary: {} };
let selectedActionPlanDetail = null;
let actionPlanLinearSort = { key: 'linear_allocation_score', direction: 'desc' };
let analysisSort = { key: 'upside', direction: 'desc' };
let portfolioFilter = 'all';
let ratingFilters = new Set();
let positionRatingFilters = new Set();
let actionPlanRatingFilters = new Set();
let actionPlanActionFilters = new Set();
let selectedAnalysisSymbols = new Set();
let analysisDetailState = null;
let analysisDetailOrigin = 'analysis';
let isEditingVariables = false;
let activeAnalysisVariableCategory = 'Core Driver';
let editableAnalysisVariables = null;
let activeScenarioOverlayTab = 'bakingmoney';
let editingExternalScenarioId = null;
let isEditingBusinessModel = false;
let isEditingBusinessSummary = false;
let currentAlertDetailId = null;
let latestAlerts = [];
let alertsStatusFilter = 'New';
let alertDetailAnalysisState = null;
let alertDetailIsEditingVariables = false;
let currentAlertNavigationIds = [];
let currentAlertDetailSymbol = null;
let isUpdatingTwsDataToggle = false;
let earningsReviewItems = [];
let earningsReviewSelectedSymbol = null;
let earningsReviewSelectedRecordId = null;
let earningsReviewSymbolHistory = null;
let earningsReviewActiveTab = 'calendar';
let earningsCalendarItems = [];
let earningsCalendarPortfolioFilter = 'all';
let earningsCalendarDateFilters = new Set();
let earningsCalendarFiscalYearFilters = new Set();
let earningsCalendarFiscalQuarterFilters = new Set();
let earningsCalendarReleaseDateSortDirection = 'asc';
let earningsCalendarAddFormDefaultsApplied = false;
const DEFAULT_SCENARIO_PROBABILITY_SETTINGS = {
  probability_source_mode: 'hybrid',
  hybrid_ai_weight: 0.70,
  hybrid_backend_weight: 0.30,
  backend_base_max_probability: 60.0,
  backend_base_min_probability: 35.0,
};

const DEFAULT_RATING_SETTINGS = {
  min_conviction_hold_threshold: 5.0,
  strong_buy_min_upside: 50.0,
  strong_buy_min_diff: 1.5,
  strong_buy_min_bullish_confidence: 7.0,
  buy_min_upside: 25.0,
  buy_min_diff: 0.5,
  buy_min_bullish_confidence: 5.5,
  speculative_buy_min_upside: 75.0,
  speculative_buy_min_diff: 0.1,
  speculative_buy_min_bullish_confidence: 4.5,
  speculative_buy_min_core_diff_floor: -0.5,
  strong_sell_max_upside: 0.0,
  strong_sell_max_diff: -1.5,
  strong_sell_min_bearish_confidence: 7.0,
  sell_max_upside: 10.0,
  sell_max_diff: -0.5,
  sell_min_bearish_confidence: 5.5,
};


const DEFAULT_ACTION_PLAN_SETTINGS = {
  action_bucket_strong_buy_target: 35.0,
  action_bucket_buy_target: 30.0,
  action_bucket_speculative_buy_target: 15.0,
  action_bucket_hold_target: 10.0,
  action_bucket_cash_target: 10.0,
  action_bucket_sell_target: 0.0,
  action_bucket_strong_sell_target: 0.0,
  action_use_dynamic_bucket_sizing: true,
  action_use_weighted_eligible_count: true,
  action_min_cash_unallocated_target: 10.0,
  action_redistribute_post_cap_excess: false,
  action_weighted_count_min_score: 0.15,
  action_weighted_count_full_score: 0.75,
  action_weighted_count_max_contribution: 1.0,
  action_max_potential_score_contribution: 0.20,
  action_allocation_upside_weight: 0.60,
  action_allocation_core_weight: 0.30,
  action_allocation_potential_weight: 0.10,
  action_allocation_risk_penalty_strength: 0.60,
  action_bucket_sizing_upside_weight: 0.50,
  action_bucket_sizing_core_weight: 0.40,
  action_bucket_sizing_potential_weight: 0.10,
  action_bucket_sizing_risk_penalty_strength: 0.50,
  action_strong_buy_weight_per_effective_stock: 5.0,
  action_strong_buy_max_effective_count: 6.0,
  action_strong_buy_max_bucket_target: 45.0,
  action_strong_buy_compression_weight: 0.25,
  action_buy_weight_per_effective_stock: 2.5,
  action_buy_max_effective_count: 14.0,
  action_buy_max_bucket_target: 35.0,
  action_buy_compression_weight: 0.75,
  action_speculative_buy_weight_per_effective_stock: 1.5,
  action_speculative_buy_max_effective_count: 5.0,
  action_speculative_buy_max_bucket_target: 7.5,
  action_speculative_buy_compression_weight: 1.25,
  action_hold_weight_per_effective_stock: 0.8,
  action_hold_max_effective_count: 15.0,
  action_hold_max_bucket_target: 12.0,
  action_hold_compression_weight: 2.0,
  action_include_current_positions: true,
  action_include_strong_buy: true,
  action_include_buy: true,
  action_include_speculative_buy: true,
  action_include_hold_only_if_owned: true,
  action_include_sell_only_if_owned: true,
  action_redistribute_capped_excess: false,
  action_allow_bucket_underallocation: true,
  action_show_unallocated_bucket_amount: true,
  action_upside_zero_score: 10.0,
  action_upside_full_score: 100.0,
  action_core_diff_zero_score: -0.5,
  action_core_diff_full_score: 2.0,
  action_core_bearish_penalty_start: 5.0,
  action_core_bearish_penalty_full: 8.0,
  action_max_potential_bonus_weight: 2.0,
  action_potential_diff_minimum: 0.25,
  action_potential_diff_full_score: 2.0,
  action_potential_bullish_confidence_minimum: 4.5,
  action_potential_bonus_upside_minimum: 50.0,
  action_max_single_stock_weight: 8.0,
  action_max_strong_buy_stock_weight: 8.0,
  action_max_buy_stock_weight: 6.0,
  action_max_speculative_buy_stock_weight: 3.0,
  action_max_negative_core_weight: 2.0,
  action_max_very_negative_core_weight: 1.0,
  action_min_target_weight_to_show: 0.5,
  action_band_lower_multiplier: 0.8,
  action_band_upper_multiplier: 1.2,
  action_target_band_lower_multiplier: 0.8,
  action_target_band_upper_multiplier: 1.2,
  action_speculative_band_lower_multiplier: 0.7,
  action_speculative_band_upper_multiplier: 1.3,
  action_min_absolute_band_width: 0.5,
  action_strong_add_below_target_multiplier: 0.5,
  action_strong_trim_above_target_multiplier: 1.5,
  action_min_trade_gap_percent: 0.5,
  action_min_executable_trade_amount: 100.0,
  action_starter_buy_max_initial_weight: 1.0,
  action_use_allocation_based_triggers: true,
  action_momentum_add_max_raise: 0.08,
  action_momentum_add_max_lower: 0.10,
  action_extension_add_max_lower: 0.10,
  action_momentum_trim_max_raise: 0.15,
  action_momentum_trim_max_lower: 0.10,
  action_extension_trim_max_lower: 0.15,
  action_min_trigger_multiplier: 0.75,
  action_max_trigger_multiplier: 1.25,
  action_add_required_upside: 30.0,
  action_strong_add_required_upside: 50.0,
  action_starter_buy_required_upside: 75.0,
  action_trim_remaining_upside: 10.0,
  action_sell_remaining_upside: 0.0,
  action_starter_buy_base_required_upside: 0.25,
  action_add_base_required_upside: 0.30,
  action_strong_add_base_required_upside: 0.40,
  action_hold_extra_add_required_upside: 0.50,
  action_trim_remaining_upside_threshold: 0.10,
  action_sell_remaining_upside_threshold: 0.00,
  action_underweight_discount_max: 0.10,
  action_quality_discount_max: 0.10,
  action_overweight_penalty_max: 0.15,
  action_low_quality_penalty_max: 0.15,
  action_trigger_min_required_upside: 0.10,
  action_trigger_max_required_upside: 0.80,
  action_strong_trim_gap_threshold: 0.25,
  action_treat_cash_equivalents_as_cash: true,
  action_cash_equivalent_symbols: 'SGOV',
  linear_allocated_target_total_pct: 100.0,
  linear_reserve_benchmark_yield_pct: 4.0,
  linear_min_equity_excess_cagr_pct: 2.0,
  linear_full_attractiveness_equity_excess_cagr_pct: 7.0,
  linear_max_reserve_pct: 40.0,
  linear_min_expected_cagr: 0.0,
  linear_full_expected_cagr: 15.0,
  linear_min_upside: 0.0,
  linear_full_upside: 80.0,
  linear_min_core_net: -1.0,
  linear_full_core_net: 2.0,
  linear_min_potential_net: -1.0,
  linear_full_potential_net: 1.5,
  linear_expected_cagr_weight: 40.0,
  linear_upside_weight: 20.0,
  linear_core_confidence_weight: 25.0,
  linear_potential_confidence_weight: 10.0,
  linear_confidence_quality_weight: 5.0,
  linear_min_score_threshold: 0.10,
  linear_score_allocation_power: 1.5,
  linear_zero_target_if_expected_cagr_negative: true,
  linear_zero_target_if_upside_negative: true,
  linear_max_single_stock_pct: 10.0,
  linear_target_band_tolerance_pct: 15.0,
  linear_add_band_tolerance_pct: 15.0,
  linear_trim_band_tolerance_pct: 30.0,
  linear_enable_risk_caps: true,
  linear_negative_core_net_cap_pct: 2.0,
  linear_low_core_net_threshold: 0.5,
  linear_low_core_net_cap_pct: 4.0,
  linear_high_bearish_confidence_min_threshold: 4.0,
  linear_high_bearish_confidence_max_threshold: 8.0,
  linear_high_bearish_confidence_cap_pct: 5.0,
  core_confidence_penalty_threshold: 0.5,
  core_confidence_penalty: 0.15,
  upside_penalty_threshold: 40.0,
  upside_penalty: 0.20,
  potential_confidence_penalty_threshold: 0.0,
  potential_confidence_penalty: 0.05,
  hold_rating_penalty_enabled: true,
  hold_rating_penalty: 0.10,
  linear_rating_bonus_enabled: true,
  linear_strong_buy_rating_bonus: 0.05,
  linear_buy_rating_bonus: 0.02,
  linear_frontier_optionality_max_boost_pct: 10.0,
  linear_block_buy_actions_for_hold_rating: true,
  linear_high_extension_guardrail_enabled: true,
  linear_high_extension_risk_threshold: 4.0,
  linear_release_date_warning_days: 30,
};

const FRONTIER_SCORE_OPTIONS = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5];

const CONFIG_HELP = {};
let lastConfigHelpTrigger = null;

function addConfigHelp(key, help) {
  CONFIG_HELP[key] = help;
}

function registerActionPlanConfigHelp() {
  addConfigHelp('ib_delayed_price_extra_wait_seconds', {
    title: 'Delayed price extra wait time for IB/TWS',
    meaning: 'Additional polling time used when TWS indicates delayed market data is being returned.',
    usedIn: 'Analysis → Update Current Prices. The app adds this extra wait only after delayed/partial market-data warnings so slower delayed prices have more time to populate.',
    tuning: 'Default 5 seconds. Increase if delayed prices often arrive late; keep at 0 if you want the refresh to use only the base IB/TWS price wait time.',
    related: ['Price wait time for IB/TWS', 'Update Current Prices'],
  });

  addConfigHelp('action_use_dynamic_bucket_sizing', {
    title: 'Use dynamic bucket sizing',
    meaning: 'Turns on the dynamic Action Plan bucket model instead of fixed bucket percentages.',
    usedIn: 'Used when the Action Plan decides each rating bucket target before company-level allocation.',
    formula: 'Dynamic mode: Raw Bucket Target = min(Weighted Count Used × Weight / Effective Stock, Max Bucket Target)',
    example: 'When enabled, a Buy bucket with more qualified opportunities grows automatically instead of using a fixed Buy bucket percentage.',
    tuning: 'Keep this enabled for the intended model. Turn it off only to fall back to legacy fixed bucket targets.',
    related: ['Weighted Count settings', 'Bucket weight/effective stock', 'Max bucket %'],
  });
  addConfigHelp('action_use_weighted_eligible_count', {
    title: 'Use weighted eligible count',
    meaning: 'Counts companies by opportunity quality instead of treating every eligible company as exactly one full stock.',
    usedIn: 'Used in dynamic bucket sizing to decide how much each bucket expands.',
    formula: 'Weighted Count = clamp((Bucket Sizing Score - Min Score) / (Full Score - Min Score), 0, Max Contribution)',
    example: 'A company with a medium Bucket Sizing Score might count as 0.50 effective stocks.',
    tuning: 'Keep enabled when you want weak opportunities to expand buckets less than strong opportunities.',
    related: ['Weighted Count Min Score', 'Weighted Count Full Score', 'Bucket Sizing Score'],
  });
  addConfigHelp('action_min_cash_unallocated_target', {
    title: 'Minimum cash/unallocated %',
    meaning: 'Minimum percentage kept in cash or unallocated capacity even when equity opportunities are very attractive.',
    usedIn: 'Used in bucket reconciliation and cash-constrained execution, and reused as the minimum Dynamic Reserve for Linear Allocation.',
    formula: 'Available Buy Budget = Cash-like Available + Executable Sell/Trim Proceeds - Protected Reserve (minimum reserve for Bucket, Dynamic Reserve for Linear)',
    example: 'With a $100,000 portfolio and 10% reserve, the execution layer protects $10,000 before funding adds.',
    tuning: 'Increase this to keep more liquidity. Decrease it to allow more capital to be deployed into stock targets.',
    related: ['Cash-equivalent symbols', 'Minimum executable trade amount'],
  });
  addConfigHelp('action_min_executable_trade_amount', {
    title: 'Minimum executable trade amount',
    meaning: 'Minimum dollar amount for a buy/add recommendation to be considered practical to execute now.',
    usedIn: 'Used only by the cash-constrained execution layer; it does not change target allocations.',
    formula: 'If an allocated buy amount is below this threshold, it is usually marked Unfunded / Watch.',
    example: 'If only $40 remains after higher-priority adds and this setting is $100, the remaining add is not recommended as an executable trade.',
    tuning: 'Raise this to avoid tiny trades. Lower it if you are comfortable with smaller incremental adds.',
    related: ['Available Buy Budget', 'Total Add Demand', 'Funding Status'],
  });
  addConfigHelp('linear_release_date_warning_days', {
    title: 'Linear release date warning days',
    meaning: 'Shows an informational warning beside a Linear Allocation release date that is near.',
    usedIn: 'Action Plan → Linear Allocation Release Date column only. It does not change actions, targets, funding, scores, or guardrails.',
    formula: 'Show when 0 ≤ calendar days until the stored release date ≤ this setting.',
    example: 'With 30 days configured, a release date 30 days ahead shows a warning. Set to 0 to disable warnings.',
    tuning: 'Default 30 days. Use a shorter window for fewer reminders.',
    related: ['Release Date', 'Earnings Calendar'],
  });
  addConfigHelp('action_weighted_count_min_score', {
    title: 'Weighted Count Min Score',
    meaning: 'Minimum Bucket Sizing Score needed before a company expands its bucket.',
    usedIn: 'Converts Bucket Sizing Score into Weighted Count for bucket expansion.',
    formula: 'Weighted Count = clamp((Bucket Sizing Score - Min Score) / (Full Score - Min Score), 0, Max Contribution)',
    example: 'Min score 0.15, full score 0.75, Bucket Sizing Score 0.45 → Weighted Count 0.50.',
    tuning: 'Increase to make bucket growth more selective. Decrease to let moderate opportunities expand buckets sooner.',
    related: ['Weighted Count Full Score', 'Weighted Count Max Contribution', 'Bucket Sizing Score'],
  });
  addConfigHelp('action_weighted_count_full_score', {
    title: 'Weighted Count Full Score',
    meaning: 'Bucket Sizing Score where a company counts as one full effective stock.',
    usedIn: 'Used with Min Score to scale Weighted Count gradually.',
    formula: 'Weighted Count reaches Max Contribution when Bucket Sizing Score reaches this value.',
    example: 'If Full Score is 0.75, a company scoring 0.75 or higher can count as one full effective stock.',
    tuning: 'Raise this to require stronger opportunities for full bucket expansion. Lower it to fill buckets faster.',
    related: ['Weighted Count Min Score', 'Weighted Count Max Contribution'],
  });
  addConfigHelp('action_weighted_count_max_contribution', {
    title: 'Weighted Count Max Contribution',
    meaning: 'Maximum bucket-expansion contribution per company.',
    usedIn: 'Caps row-level Weighted Count before it is summed into a bucket total.',
    formula: 'Weighted Count is clamped to this maximum contribution.',
    example: 'A max contribution of 1.00 means no single company can expand a bucket by more than one effective stock.',
    tuning: 'Usually keep at 1.00. Lower values make bucket growth more diversified across more names.',
    related: ['Bucket Sizing Score', 'Max Effective Count'],
  });

  [
    ['action_allocation_upside_weight', 'Allocation upside weight', 'how directly upside influences company allocation inside a bucket'],
    ['action_allocation_core_weight', 'Allocation core weight', 'how much core conviction influences company allocation inside a bucket'],
    ['action_allocation_potential_weight', 'Allocation potential weight', 'how much potential-driver conviction influences company allocation inside a bucket'],
  ].forEach(([key, title, meaning]) => addConfigHelp(key, {
    title,
    meaning: `Controls ${meaning}. Allocation weights are normalized internally if they do not sum to 1.0.`,
    usedIn: 'Used by Allocation Score, which distributes each bucket across companies.',
    formula: 'Allocation Score = (upside weight × upside score + core weight × core conviction score + potential weight × potential conviction score) × allocation risk modifier',
    example: 'Higher upside weight gives high-upside companies a larger share of the bucket even when conviction is moderate.',
    tuning: 'Increase this weight to emphasize the factor; decrease it to rely more on the other allocation factors.',
    related: ['Allocation risk penalty strength', 'Bucket Sizing Score weights'],
  }));
  addConfigHelp('action_allocation_risk_penalty_strength', {
    title: 'Allocation risk penalty strength',
    meaning: 'Controls how strongly bearish core confidence reduces Allocation Score.',
    usedIn: 'Used after the weighted Allocation Score blend.',
    formula: 'Allocation Risk Modifier = 1 - ((1 - Core Risk Modifier) × Risk Penalty Strength)',
    example: 'If Core Risk Modifier is 0.50 and strength is 0.60, Allocation Risk Modifier is 0.70.',
    tuning: 'Increase to penalize bearish-core names more. Decrease to let upside and potential contribute more despite core risk.',
    related: ['Core bearish penalty start', 'Core bearish penalty full'],
  });
  [
    ['action_bucket_sizing_upside_weight', 'Bucket sizing upside weight', 'upside'],
    ['action_bucket_sizing_core_weight', 'Bucket sizing core weight', 'core conviction'],
    ['action_bucket_sizing_potential_weight', 'Bucket sizing potential weight', 'potential conviction'],
  ].forEach(([key, title, factor]) => addConfigHelp(key, {
    title,
    meaning: `Controls how much ${factor} contributes to Bucket Sizing Score.`,
    usedIn: 'Used by Bucket Sizing Score, which controls Weighted Count and bucket expansion.',
    formula: 'Bucket Sizing Score = (upside weight × upside score + core weight × core conviction score + potential weight × potential conviction score) × bucket sizing risk modifier',
    example: 'Increasing the upside weight lets companies with attractive upside expand buckets more, even if Allocation Score remains stricter.',
    tuning: 'Tune separately from Allocation Score. Bucket sizing decides how large buckets become; allocation score decides how that bucket is split.',
    related: ['Weighted Count Min Score', 'Allocation Score weights'],
  }));
  addConfigHelp('action_bucket_sizing_risk_penalty_strength', {
    title: 'Bucket sizing risk penalty strength',
    meaning: 'Controls how much core risk reduces Bucket Sizing Score.',
    usedIn: 'Used before converting Bucket Sizing Score into Weighted Count.',
    formula: 'Bucket Sizing Risk Modifier = 1 - ((1 - Core Risk Modifier) × Risk Penalty Strength)',
    example: 'With strength 0.50, a core risk modifier of 0.50 becomes a milder bucket sizing modifier of 0.75.',
    tuning: 'Increase to make risky names expand buckets less. Decrease to make bucket sizing more opportunity-driven.',
    related: ['Allocation risk penalty strength', 'Weighted Count'],
  });

  ['Strong Buy', 'Buy', 'Speculative Buy', 'Hold'].forEach((bucket) => {
    const prefix = bucket.toLowerCase().replace(/ /g, '_');
    addConfigHelp(`action_${prefix}_weight_per_effective_stock`, {
      title: `${bucket} weight/effective stock`,
      meaning: `Percentage target added to the ${bucket} bucket for each 1.00 effective weighted stock.`,
      usedIn: `Used in the dynamic ${bucket} raw bucket target calculation.`,
      formula: 'Uncapped Bucket Target = Weighted Count Used × Weight / Effective Stock',
      example: `Weighted Count Used = 8 and ${bucket} weight/effective stock = 10% → Uncapped Bucket Target = 80%.`,
      tuning: `Increase to make the ${bucket} bucket grow faster as more companies qualify. Decrease to keep the bucket smaller.`,
      related: [`${bucket} max effective count`, `${bucket} max bucket %`],
    });
    addConfigHelp(`action_${prefix}_max_effective_count`, {
      title: `${bucket} max effective count`,
      meaning: `Caps how many weighted opportunities can expand the ${bucket} bucket.`,
      usedIn: `Used before multiplying by ${bucket} weight/effective stock.`,
      formula: 'Weighted Count Used = min(Total Weighted Eligible Count, Max Effective Count)',
      example: 'Total Weighted Eligible Count = 14 and Max Effective Count = 10 → Weighted Count Used = 10.',
      tuning: `Increase to let many ${bucket} opportunities expand the bucket. Decrease to limit concentration in this bucket.`,
      related: [`${bucket} weight/effective stock`, `${bucket} max bucket %`],
    });
    addConfigHelp(`action_${prefix}_max_bucket_target`, {
      title: `${bucket} max bucket %`,
      meaning: `Maximum portfolio percentage the ${bucket} bucket can receive before compression.`,
      usedIn: `Caps the dynamic ${bucket} raw bucket target.`,
      formula: 'Raw Bucket Target = min(Uncapped Bucket Target, Max Bucket Target)',
      example: 'Uncapped Bucket Target = 120% and Max Bucket = 75% → Raw Bucket Target = 75%.',
      tuning: `Increase to allow more exposure to ${bucket} names. Decrease to cap this bucket more tightly.`,
      related: [`${bucket} max effective count`, `${bucket} compression weight`],
    });
    addConfigHelp(`action_${prefix}_compression_weight`, {
      title: `${bucket} compression weight`,
      meaning: `Controls how much the ${bucket} bucket is reduced when total raw equity demand exceeds available portfolio capacity.`,
      usedIn: 'Used in bucket reconciliation/compression.',
      formula: 'Bucket Compression is proportional to Raw Bucket Target × Compression Weight',
      example: 'A higher compression weight means this bucket gives up more allocation when raw demand exceeds capacity.',
      tuning: 'Lower values protect a bucket during compression; higher values make it shrink more.',
      related: ['Minimum cash/unallocated %', 'Raw Equity Demand'],
    });
  });

  [
    ['action_max_single_stock_weight', 'Max single-stock weight %', 'the maximum allowed target for any individual stock'],
    ['action_max_strong_buy_stock_weight', 'Max Strong Buy stock weight %', 'the max target for a Strong Buy stock'],
    ['action_max_buy_stock_weight', 'Max Buy stock weight %', 'the max target for a Buy stock'],
    ['action_max_speculative_buy_stock_weight', 'Max Speculative Buy stock weight %', 'the max target for a Speculative Buy stock'],
    ['action_max_negative_core_weight', 'Max negative-core stock weight %', 'the max target when core confidence is negative'],
    ['action_max_very_negative_core_weight', 'Max very-negative-core stock weight %', 'the max target when core confidence is very negative'],
  ].forEach(([key, title, meaning]) => addConfigHelp(key, {
    title,
    meaning: `Controls ${meaning}. The effective stock cap is usually the minimum applicable cap.`,
    usedIn: 'Applied after target-mid-before-caps is calculated.',
    formula: 'Target Mid After Caps = min(Target Mid Before Caps, applicable caps)',
    example: 'If max single-stock weight is 8% and max Strong Buy stock weight is 15%, the effective Strong Buy cap is 8%.',
    tuning: 'Increase to allow larger individual positions. Decrease to force more diversification or risk control.',
    related: ['Target Mid Before Caps', 'Cap Reason'],
  }));

  addConfigHelp('action_upside_zero_score', {
    title: 'Upside zero score %',
    meaning: 'Upside percentage that maps to an upside score of 0.00.',
    usedIn: 'Used by both Allocation Score and Bucket Sizing Score.',
    formula: 'Upside Score = clamp((Upside - Zero Score) / (Full Score - Zero Score), 0, 1)',
    example: 'If zero is 10% and full is 100%, then 10% upside maps to 0.00.',
    tuning: 'Raise this to require more upside before a company gets any upside-score credit.',
    related: ['Upside full score %'],
  });
  addConfigHelp('action_upside_full_score', {
    title: 'Upside full score %',
    meaning: 'Upside percentage that maps to a full upside score of 1.00.',
    usedIn: 'Used by both Allocation Score and Bucket Sizing Score.',
    formula: 'Upside Score = clamp((Upside - Zero Score) / (Full Score - Zero Score), 0, 1)',
    example: 'If zero is 10% and full is 100%, then 55% upside maps to about 0.50 and 100% maps to 1.00.',
    tuning: 'If too low, upside stops differentiating high-upside companies. If too high, upside contributes more gradually.',
    related: ['Upside zero score %'],
  });

  [
    ['action_starter_buy_base_required_upside', 'Starter Buy base required upside', 'base upside required before a starter buy is attractive'],
    ['action_add_base_required_upside', 'Add base required upside', 'base upside required before adding to an underweight position'],
    ['action_strong_add_base_required_upside', 'Strong Add base required upside', 'base upside required before a high-priority add'],
    ['action_trim_remaining_upside_threshold', 'Trim remaining upside threshold', 'remaining upside threshold where trimming becomes reasonable'],
    ['action_sell_remaining_upside_threshold', 'Sell remaining upside threshold', 'remaining upside threshold where selling becomes reasonable'],
    ['action_underweight_discount_max', 'Underweight discount max', 'maximum reduction to required upside when a position is under target'],
    ['action_quality_discount_max', 'Quality discount max', 'maximum reduction to required upside for higher-quality opportunities'],
    ['action_overweight_penalty_max', 'Overweight penalty max', 'maximum increase to required upside when a position is already overweight'],
    ['action_low_quality_penalty_max', 'Low-quality penalty max', 'maximum increase to required upside for lower-quality opportunities'],
    ['action_trigger_min_required_upside', 'Trigger min required upside', 'minimum dynamic required upside after adjustments'],
    ['action_trigger_max_required_upside', 'Trigger max required upside', 'maximum dynamic required upside after adjustments'],
  ].forEach(([key, title, meaning]) => addConfigHelp(key, {
    title,
    meaning: `Controls ${meaning}.`,
    usedIn: 'Used by allocation-aware trigger price and action gating logic, not by long-term target allocation.',
    formula: 'Trigger Price = Expected Price / (1 + Dynamic Required Upside)',
    example: 'If expected price is $100 and dynamic required upside is 25%, the add trigger is $80.',
    tuning: 'Higher required upside makes buys more selective. Lower required upside makes actions execute sooner.',
    related: ['Trigger quality score', 'Target band', 'Current weight'],
  }));


  addConfigHelp('core_confidence_penalty_threshold', {
    title: 'Core confidence penalty threshold',
    meaning: 'Core Net confidence level below which the Linear Allocation model applies the core confidence penalty.',
    usedIn: 'Used in Linear Allocation scoring after the base Linear Score components are calculated. If Core Net confidence is below this threshold, the core confidence penalty factor is applied.',
    formula: 'If Core Net < threshold, score factor *= (1 - core_confidence_penalty)',
    example: 'If the threshold is 0.5 and a stock has Core Net 0.2, the core confidence penalty is triggered.',
    tuning: 'Raise this threshold to penalize more stocks with only moderate core confidence. Lower it to penalize only clearly weak or negative core-confidence stocks. A reasonable default is 0.5.',
    related: ['Core confidence penalty', 'Linear core confidence weight', 'Linear low core net cap %'],
  });

  addConfigHelp('core_confidence_penalty', {
    title: 'Core confidence penalty',
    meaning: 'Multiplicative penalty applied to the Linear Score when Core Net confidence is below the configured threshold.',
    usedIn: 'Used in the Linear Allocation penalty factor. This reduces the final score for stocks where core business drivers are not strong enough. Multiple triggered penalties compound multiplicatively.',
    formula: 'Penalty factor *= (1 - core_confidence_penalty)',
    example: 'If the penalty is 0.15, a stock that triggers this rule keeps 85% of its pre-penalty Linear Score. If it also triggers a 0.20 upside penalty, the combined factor is 0.85 × 0.80 = 0.68.',
    tuning: 'Increase this to make Linear Allocation more conservative toward weak-core-confidence names. Decrease it if the penalty is too harsh. Typical range: 0.10 to 0.25.',
    related: ['Core confidence penalty threshold', 'Linear core confidence weight', 'Linear risk caps'],
  });

  addConfigHelp('upside_penalty_threshold', {
    title: 'Upside penalty threshold %',
    meaning: 'Upside level below which the Linear Allocation model applies the upside penalty.',
    usedIn: 'Used after the base Linear Score is calculated. If scenario upside is below this threshold, the upside penalty factor is applied.',
    formula: 'If Upside < threshold, score factor *= (1 - upside_penalty)',
    example: 'If the threshold is 40% and a stock has 25% upside, the upside penalty is triggered.',
    tuning: 'Raise this threshold if you want Linear Allocation to penalize lower-upside stocks more aggressively. Lower it if you want high-confidence but moderate-upside stocks to remain competitive. A reasonable range is 25% to 50%.',
    related: ['Upside penalty', 'Linear upside weight', 'Linear expected CAGR weight'],
  });

  addConfigHelp('upside_penalty', {
    title: 'Upside penalty',
    meaning: 'Multiplicative penalty applied to the Linear Score when upside is below the configured upside threshold.',
    usedIn: 'Used in Linear Allocation scoring to reduce allocation to stocks where expected upside is not attractive enough, even if confidence is decent.',
    formula: 'Penalty factor *= (1 - upside_penalty)',
    example: 'If the penalty is 0.20, a stock that triggers this rule keeps 80% of its pre-penalty Linear Score.',
    tuning: 'Increase this if the model is allocating too much to lower-upside stocks. Decrease it if the model is unfairly punishing high-quality compounders with moderate upside. Typical range: 0.10 to 0.25.',
    related: ['Upside penalty threshold %', 'Linear full upside %', 'Linear expected CAGR weight'],
  });

  addConfigHelp('potential_confidence_penalty_threshold', {
    title: 'Potential confidence penalty threshold',
    meaning: 'Potential Net confidence level below which the Linear Allocation model applies the potential confidence penalty.',
    usedIn: 'Used after the base Linear Score is calculated. If Potential Net confidence is below this threshold, the potential confidence penalty factor is applied.',
    formula: 'If Potential Net < threshold, score factor *= (1 - potential_confidence_penalty)',
    example: 'If the threshold is 0 and a stock has Potential Net -0.3, the potential confidence penalty is triggered.',
    tuning: 'Use 0 if negative optionality should be penalized. Raise it if you want the model to require positive optionality. Lower it if Potential Drivers should matter less in allocation sizing.',
    related: ['Potential confidence penalty', 'Linear potential confidence weight', 'Linear min potential net'],
  });

  addConfigHelp('potential_confidence_penalty', {
    title: 'Potential confidence penalty',
    meaning: 'Multiplicative penalty applied to the Linear Score when Potential Net confidence is below the configured threshold.',
    usedIn: 'Used in Linear Allocation scoring to reduce allocation to stocks with weak or negative optionality.',
    formula: 'Penalty factor *= (1 - potential_confidence_penalty)',
    example: 'If the penalty is 0.05, a stock that triggers this rule keeps 95% of its pre-penalty Linear Score.',
    tuning: 'Keep this smaller than the core confidence penalty because Potential Drivers should usually matter less than Core Drivers. Typical range: 0.03 to 0.10.',
    related: ['Potential confidence penalty threshold', 'Linear potential confidence weight'],
  });

  addConfigHelp('hold_rating_penalty_enabled', {
    title: 'Enable Hold rating penalty',
    meaning: 'Turns on an extra Linear Score penalty for stocks currently rated Hold.',
    usedIn: 'Used in Linear Allocation scoring after the base score is calculated. Rating is not used to size buckets in Linear Allocation, but this option allows Hold-rated stocks to receive a modest score penalty.',
    formula: 'If enabled and Rating = Hold, score factor *= (1 - hold_rating_penalty)',
    example: 'If this is enabled and the Hold rating penalty is 0.10, a Hold-rated stock keeps 90% of its pre-penalty Linear Score.',
    tuning: 'Keep enabled if Hold-rated stocks should generally receive less allocation than Buy or Strong Buy stocks with similar metrics. Disable it if Linear Allocation should be fully independent from rating and rely only on upside, CAGR, and confidence metrics.',
    related: ['Hold rating penalty', 'Linear Score', 'Rating Settings'],
  });

  addConfigHelp('hold_rating_penalty', {
    title: 'Hold rating penalty',
    meaning: 'Multiplicative penalty applied to the Linear Score for stocks rated Hold when Hold rating penalty is enabled.',
    usedIn: 'Used in Linear Allocation scoring as a modest rating-context adjustment. It does not create buckets and does not use bucket allocation logic.',
    formula: 'Penalty factor *= (1 - hold_rating_penalty)',
    example: 'If the penalty is 0.10, a Hold-rated stock keeps 90% of its pre-penalty Linear Score.',
    tuning: 'Use a small value if you want rating to remain only a secondary context signal. A reasonable range is 0.05 to 0.15. Set to 0 or disable the checkbox if rating should have no effect on Linear Allocation.',
    related: ['Enable Hold rating penalty', 'Linear min score threshold', 'Rating Settings'],
  });

  addConfigHelp('linear_rating_bonus_enabled', {
    title: 'Enable linear rating bonus',
    meaning: 'Turns on a small multiplicative Linear Score bonus for stocks rated Strong Buy or Buy.',
    usedIn: 'Used only in Linear Allocation scoring after the base score and penalty factors are calculated. It does not affect Bucket Allocation and does not create rating buckets.',
    formula: 'If enabled, Final Linear Score = Penalty-adjusted Linear Score × Rating Bonus Factor.',
    example: 'If a Strong Buy stock has a penalty-adjusted score of 0.80 and the Strong Buy bonus is 0.05, the final score becomes 0.84.',
    tuning: 'Keep enabled if you want the Linear Allocation model to modestly reward ratings that already summarize strong upside and confidence. Disable it if you want Linear Allocation to be fully independent from rating.',
    related: ['Strong Buy rating bonus', 'Buy rating bonus', 'Hold rating penalty'],
  });

  addConfigHelp('linear_strong_buy_rating_bonus', {
    title: 'Strong Buy rating bonus',
    meaning: 'Multiplicative score bonus applied to Strong Buy stocks in Linear Allocation when rating bonus is enabled.',
    usedIn: 'Used after the base Linear Score and penalty factors are calculated.',
    formula: 'If Rating = Strong Buy, score *= (1 + linear_strong_buy_rating_bonus)',
    example: 'A value of 0.05 means a Strong Buy stock keeps 105% of its penalty-adjusted Linear Score. A score of 0.80 becomes 0.84.',
    tuning: 'Keep this small. A reasonable default is 0.05. Higher values can make Linear Allocation behave too much like bucket allocation and recreate allocation cliffs.',
    related: ['Enable linear rating bonus', 'Buy rating bonus', 'Linear Score'],
  });


  addConfigHelp('action_use_allocation_based_triggers', {
    title: 'Use allocation-based triggers',
    meaning: 'Uses target allocation bands instead of remaining-upside thresholds to calculate Action Plan trigger prices.',
    usedIn: 'Action Plan trigger-price calculation. Add triggers anchor to Target Low and Trim triggers anchor to Target High; action amount still moves toward Target Mid.',
    formula: 'Existing positions use Allocation Trigger Price = Target Weight × Other Value / (Shares × (1 - Target Weight)).',
    tuning: 'Keep enabled for the allocation-based trigger system. Legacy remaining-upside trigger settings are retained only for backward compatibility.',
    related: ['Momentum trigger adjustments', 'Extension Risk trigger adjustments', 'Target Band'],
  });
  addConfigHelp('action_momentum_add_max_raise', { title: 'Momentum add max raise', meaning: 'Maximum amount healthy positive momentum can raise an Add trigger.', usedIn: 'Allocation-based Add trigger adjustment.', tuning: 'Default 0.08 allows strong healthy momentum to raise buy triggers by up to 8%.', related: ['Extension add max lower', 'Momentum Score'] });
  addConfigHelp('action_momentum_add_max_lower', { title: 'Momentum add max lower', meaning: 'Maximum amount weak momentum can lower an Add trigger.', usedIn: 'Allocation-based Add trigger adjustment.', tuning: 'Default 0.10 makes weak momentum require a lower price before adding.', related: ['Momentum Score'] });
  addConfigHelp('action_extension_add_max_lower', { title: 'Extension add max lower', meaning: 'Maximum amount Extension Risk can lower an Add trigger.', usedIn: 'Allocation-based Add trigger adjustment.', tuning: 'Default 0.10 helps avoid chasing technically extended stocks.', related: ['Extension Risk'] });
  addConfigHelp('action_momentum_trim_max_raise', { title: 'Momentum trim max raise', meaning: 'Maximum amount positive momentum can raise a Trim trigger.', usedIn: 'Allocation-based Trim trigger adjustment.', tuning: 'Default 0.15 lets strong winners run further before trimming.', related: ['Momentum Score'] });
  addConfigHelp('action_momentum_trim_max_lower', { title: 'Momentum trim max lower', meaning: 'Maximum amount weak momentum can lower a Trim trigger.', usedIn: 'Allocation-based Trim trigger adjustment.', tuning: 'Default 0.10 can trim overweight weak-momentum stocks earlier.', related: ['Momentum Score'] });
  addConfigHelp('action_extension_trim_max_lower', { title: 'Extension trim max lower', meaning: 'Maximum amount Extension Risk can lower a Trim trigger.', usedIn: 'Allocation-based Trim trigger adjustment.', tuning: 'Default 0.15 brings trim triggers lower for overextended stocks.', related: ['Extension Risk'] });
  addConfigHelp('action_min_trigger_multiplier', { title: 'Minimum trigger multiplier', meaning: 'Lower clamp for Momentum/Extension trigger adjustments.', usedIn: 'Applied after add/trim trigger multipliers are calculated.', tuning: 'Default 0.75 prevents trigger prices from being adjusted too far down.', related: ['Maximum trigger multiplier'] });
  addConfigHelp('action_max_trigger_multiplier', { title: 'Maximum trigger multiplier', meaning: 'Upper clamp for Momentum/Extension trigger adjustments.', usedIn: 'Applied after add/trim trigger multipliers are calculated.', tuning: 'Default 1.25 prevents trigger prices from being adjusted too far up.', related: ['Minimum trigger multiplier'] });

  addConfigHelp('linear_buy_rating_bonus', {
    title: 'Buy rating bonus',
    meaning: 'Small multiplicative score bonus applied to Buy-rated stocks in Linear Allocation when rating bonus is enabled.',
    usedIn: 'Used after the base Linear Score and penalty factors are calculated.',
    formula: 'If Rating = Buy, score *= (1 + linear_buy_rating_bonus)',
    example: 'A value of 0.02 means a Buy-rated stock keeps 102% of its penalty-adjusted Linear Score. A score of 0.70 becomes 0.714.',
    tuning: 'This should be smaller than the Strong Buy bonus. A reasonable default is 0.02. Keep it small so Linear Allocation remains mainly driven by expected CAGR, upside, core confidence, potential confidence, and risk penalties.',
    related: ['Enable linear rating bonus', 'Strong Buy rating bonus', 'Linear Score'],
  });

  addConfigHelp('linear_block_buy_actions_for_hold_rating', {
    title: 'Block buy actions for Hold-rated stocks',
    meaning: 'When enabled, Hold-rated stocks can keep their Linear Allocation score, target midpoint, and target band, but they cannot receive Add, Strong Add, or Starter Buy actions.',
    usedIn: 'Used only in Linear Allocation action planning after target/action classification and before cash funding. Blocked rows show Watch / Rating Guardrail and do not consume buy budget.',
    formula: 'If Rating = Hold and the row would otherwise be Add, Strong Add, or Starter Buy, action becomes Watch / Rating Guardrail.',
    example: 'A Hold-rated stock below its Linear Target Low still shows its target gap and band, but Action Amount is — and Funding shows Rating blocks add.',
    tuning: 'Keep enabled when Hold means acceptable to keep but not high-conviction enough for new capital. Disable only if you want the previous behavior where Hold-rated underweights can receive buy-side actions.',
    related: ['Hold rating penalty', 'Linear Allocation Actions', 'Rating Settings'],
  });

  addConfigHelp('linear_high_extension_guardrail_enabled', {
    title: 'Linear high extension guardrail enabled',
    meaning: 'When enabled, Linear Allocation defers Add actions for stocks with Extension Risk at or above this 0–5 threshold to avoid chasing extended moves.',
    usedIn: 'Used only after the Target Band and rating guardrail decisions, before whole-share execution and funding. Deferred rows show Watch / Extended and do not consume buy budget.',
    formula: 'If the final Target Band action is Add and Extension Risk >= linear_high_extension_risk_threshold, action becomes Watch / Extended.',
    example: 'An underweight Buy-rated stock with Extension Risk 4.3 and a threshold of 4.0 remains strategically underweight but displays Watch / Extended.',
    tuning: 'Keep enabled to defer tactical entries after extended moves. Disable it to let target-band Add actions proceed regardless of Extension Risk.',
    related: ['Linear high extension risk threshold', 'Extension Risk', 'Linear Allocation Actions'],
  });

  addConfigHelp('linear_high_extension_risk_threshold', {
    title: 'Linear high extension risk threshold',
    meaning: 'Raw 0–5 Extension Risk score at or above which the Linear high extension guardrail defers Add actions.',
    usedIn: 'Used only by the Linear high extension guardrail; it does not change Linear Score, Target Bands, or Extension Risk calculation.',
    example: 'With a threshold of 4.0, Extension Risk 4.0 or 4.3 defers an otherwise executable Add.',
    tuning: 'Default 4.0 reserves the guardrail for high Extension Risk. Lower it to defer more entries, or raise it to defer only the most extended moves.',
    related: ['Linear high extension guardrail enabled', 'Extension Risk'],
  });

  addConfigHelp('linear_allocated_target_total_pct', {
    title: 'Linear allocated target total %',
    meaning: 'Total percentage of the portfolio the Linear Allocation model is allowed to allocate to stocks. Dynamic Reserve scaling may reduce final stock exposure below this pre-reserve target.',
    usedIn: 'The linear model normalizes positive Linear Scores toward this percentage before company caps and the portfolio-wide Dynamic Reserve scaling are applied.',
    example: 'If set to 95%, Linear Allocation can allocate up to 95% to stocks and leave roughly 5% unallocated or cash-like.',
    tuning: 'Use 100% to fully allocate across stocks. Use a lower value such as 90% or 95% when you want explicit cash or unallocated capacity.',
    related: ['Linear Score', 'Linear max single-stock %', 'Minimum cash/unallocated %'],
  });

  addConfigHelp('linear_reserve_benchmark_yield_pct', {
    title: 'Linear reserve benchmark yield %',
    meaning: 'Annualized expected yield of the cash-like reserve alternative, such as SGOV. Used as the hurdle rate for measuring absolute equity attractiveness.',
    usedIn: 'Linear Allocation only, when expected five-year equity CAGR is compared with the reserve alternative.',
    formula: 'Equity Excess CAGR = Probability-weighted Expected Equity CAGR - Reserve Benchmark Yield',
    tuning: 'Keep this aligned with the annualized yield reasonably available from the reserve alternative.',
    related: ['Linear minimum equity excess CAGR %', 'Dynamic Reserve Target'],
  });

  addConfigHelp('linear_min_equity_excess_cagr_pct', {
    title: 'Linear minimum equity excess CAGR %',
    meaning: 'Minimum expected annual equity return premium above the reserve benchmark. Stocks at or below this premium contribute zero absolute attractiveness.',
    usedIn: 'Linear Allocation only, as the zero-credit point for absolute opportunity.',
    formula: 'Absolute Attractiveness = clamp((Equity Excess CAGR - Minimum Excess) / (Full Excess - Minimum Excess), 0, 1)',
    tuning: 'Raise this to require a larger equity premium before deploying reserve capital.',
    related: ['Linear reserve benchmark yield %', 'Linear full-attractiveness equity excess CAGR %'],
  });

  addConfigHelp('linear_full_attractiveness_equity_excess_cagr_pct', {
    title: 'Linear full-attractiveness equity excess CAGR %',
    meaning: 'Expected annual equity return premium above the reserve benchmark at which a stock receives full absolute-attractiveness credit.',
    usedIn: 'Linear Allocation only, as the full-credit point for absolute opportunity.',
    formula: 'Absolute Attractiveness = clamp((Equity Excess CAGR - Minimum Excess) / (Full Excess - Minimum Excess), 0, 1)',
    tuning: 'Raise this to require a larger equity premium before the Dynamic Reserve reaches its minimum.',
    related: ['Linear minimum equity excess CAGR %', 'Portfolio Opportunity Score'],
  });

  addConfigHelp('linear_max_reserve_pct', {
    title: 'Linear maximum reserve %',
    meaning: 'Maximum portfolio percentage that Linear Allocation may intentionally leave in cash or a cash-like reserve when equity opportunities are unattractive.',
    usedIn: 'Linear Allocation only, as the upper bound of the Dynamic Reserve Target.',
    formula: 'Dynamic Reserve = Minimum Reserve + (1 - Opportunity Score) x (Maximum Reserve - Minimum Reserve)',
    tuning: 'Increase this to permit a larger defensive reserve when expected returns are weak.',
    related: ['Minimum cash/unallocated %', 'Maximum Deployable Equity'],
  });

  [
    ['linear_min_expected_cagr', 'Linear min expected CAGR %', 'Expected CAGR level that receives zero score contribution from the expected-CAGR component.', 'Used to normalize expected CAGR into the Linear Score.', 'With min = 0 and full = 15, a stock with 0% expected CAGR gets no expected-CAGR contribution while 15% or higher gets full contribution.', 'Usually keep at 0%. A stock below this level receives no expected-CAGR score.'],
    ['linear_full_expected_cagr', 'Linear full expected CAGR %', 'Expected CAGR level that receives full score contribution from the expected-CAGR component.', 'Used to normalize expected CAGR into the Linear Score.', 'With min = 0 and full = 15, a stock with 7.5% expected CAGR receives about half of this component.', 'A reasonable default is 15%. Lower values make moderate-CAGR stocks score better; higher values make the model more selective.'],
    ['linear_min_upside', 'Linear min upside %', 'Upside level that receives zero score contribution from the upside component.', 'Used to normalize scenario upside into the Linear Score.', 'With min = 0, a stock at or below 0% upside receives no upside contribution.', 'Usually keep at 0%. Stocks with negative upside should normally receive no upside score.'],
    ['linear_full_upside', 'Linear full upside %', 'Upside level that receives full score contribution from the upside component.', 'Used to normalize scenario upside into the Linear Score.', 'With full upside = 80, stocks with 80%, 100%, or 150% upside all receive the maximum upside contribution.', 'A reasonable default is 80%. This prevents very high-upside but lower-confidence stocks from being over-rewarded by upside alone.'],
    ['linear_min_core_net', 'Linear min core net', 'Core Net confidence level that receives zero score contribution from the core confidence component. Negative values are valid.', 'Used to normalize Core Net confidence into the Linear Score.', 'With min = -1 and full = 2, core net -1 receives zero core score while core net 2 receives full core score.', 'A reasonable default is -1 because weak or negative core confidence should receive little or no core score.'],
    ['linear_full_core_net', 'Linear full core net', 'Core Net confidence level that receives full score contribution from the core confidence component.', 'Used to normalize Core Net confidence into the Linear Score.', 'With min = -1 and full = 2, core net 0.5 receives about half of this component.', 'A reasonable default is 2. Lower values give full core-confidence credit sooner; higher values make the model more selective.'],
    ['linear_min_potential_net', 'Linear min potential net', 'Potential Net confidence level that receives zero score contribution from the potential confidence component. Negative values are valid.', 'Used to normalize Potential Net confidence into the Linear Score.', 'With min = -1 and full = 1.5, potential net -1 receives zero potential score while 1.5 receives full score.', 'A reasonable default is -1 because negative optionality should reduce the score.'],
    ['linear_full_potential_net', 'Linear full potential net', 'Potential Net confidence level that receives full score contribution from the potential confidence component.', 'Used to normalize Potential Net confidence into the Linear Score.', 'With min = -1 and full = 1.5, potential net 0.25 receives about half of this component.', 'A reasonable default is 1.5. Potential confidence should matter, but usually should not dominate allocation sizing.'],
  ].forEach(([key, title, meaning, usedIn, example, tuning]) => addConfigHelp(key, {
    title,
    meaning,
    usedIn,
    formula: 'Component Score = clamp((Value - Min) / (Full - Min), 0, 1)',
    example,
    tuning,
    related: ['Linear Score', 'Linear component weights'],
  }));

  [
    ['linear_expected_cagr_weight', 'Linear expected CAGR weight', 'How much the expected-CAGR component contributes to the Linear Score.', 'Higher values make the model more return-driven. Lower values make confidence and quality more important. A disciplined default is around 30.'],
    ['linear_upside_weight', 'Linear upside weight', 'How much raw upside contributes to the Linear Score.', 'Keep this relatively low because expected CAGR already captures expected return. A high upside weight can over-rank high-upside stocks with weaker confidence. A disciplined default is around 5.'],
    ['linear_core_confidence_weight', 'Linear core confidence weight', 'How much Core Net confidence contributes to the Linear Score.', 'This should usually be the largest or one of the largest weights because Core Drivers should dominate the Base case and position sizing. A disciplined default is around 45 to 50.'],
    ['linear_potential_confidence_weight', 'Linear potential confidence weight', 'How much Potential Net confidence contributes to the Linear Score.', 'Potential Drivers should matter but not dominate. They mainly represent optionality and Bear/Bull asymmetry. A reasonable default is around 10.'],
    ['linear_confidence_quality_weight', 'Linear confidence quality weight', 'How much additional confidence-quality adjustment contributes to the Linear Score.', 'Use this to improve risk adjustment. A reasonable default is 5 to 10.'],
  ].forEach(([key, title, meaning, tuning]) => addConfigHelp(key, {
    title,
    meaning,
    usedIn: key === 'linear_confidence_quality_weight'
      ? 'Used in the Linear Score to reward strong bullish confidence and penalize high bearish confidence.'
      : 'Used as one weighted part of the Linear Score calculation. Linear weights are normalized internally by their total.',
    formula: 'Linear Score = weighted blend of expected CAGR, upside, Core Net, Potential Net, and confidence quality components.',
    example: key === 'linear_confidence_quality_weight'
      ? 'A stock with high bullish core confidence and low bearish core confidence receives a better confidence-quality contribution.'
      : 'Increasing this weight gives the factor more influence relative to the other Linear Score components.',
    tuning,
    related: ['Linear Score', 'Linear min/full score inputs'],
  }));

  addConfigHelp('linear_score_allocation_power', {
    title: 'Linear score allocation power',
    meaning: 'Controls how strongly Linear Allocation concentrates target weights into higher-scoring stocks.',
    usedIn: 'Used after Linear Score is calculated, when translating scores into target allocation weights. It does not change the Linear Score itself; it changes how much target weight each score receives.',
    formula: 'Allocation Weight = max(0, Linear Score - Min Score Threshold) ^ Allocation Power',
    example: 'With power 1.0, a score of 0.70 receives about twice the allocation weight of 0.35. With power 2.0, 0.70 receives about four times the allocation weight of 0.35.',
    tuning: 'Use 1.0 for a flatter, more diversified model. Use 1.5 as a balanced default. Use 2.0 or higher for stronger concentration in top-scoring names.',
    related: ['Linear Score', 'Linear min score threshold', 'Linear max single-stock %'],
  });

  addConfigHelp('linear_min_score_threshold', {
    title: 'Linear min score threshold',
    meaning: 'Minimum Linear Score required for a stock to receive a non-zero target allocation.',
    usedIn: 'After calculating Linear Score, stocks below this threshold receive a zero target before final target normalization.',
    formula: 'If Linear Score < Threshold, Linear Target Mid = 0 before redistribution.',
    example: 'At 0.10, a stock scoring 0.08 receives no target allocation even if it is otherwise eligible.',
    tuning: 'Raise this to make the model more selective. Lower it to allow more stocks to receive small target weights. A reasonable default is 0.10.',
    related: ['Linear Score', 'Linear allocated target total %'],
  });

  addConfigHelp('linear_zero_target_if_expected_cagr_negative', {
    title: 'Zero target if expected CAGR negative',
    meaning: 'When enabled, stocks with negative expected CAGR receive a zero target allocation regardless of other scores.',
    usedIn: 'Applied as a Linear Allocation eligibility rule before final target normalization.',
    example: 'A stock with strong confidence but -2% expected CAGR is assigned a zero target when this is enabled.',
    tuning: 'Usually keep enabled. A stock with negative expected CAGR should generally not receive fresh allocation.',
    related: ['Linear min expected CAGR %', 'Linear Score'],
  });

  addConfigHelp('linear_zero_target_if_upside_negative', {
    title: 'Zero target if upside negative',
    meaning: 'When enabled, stocks with negative upside receive a zero target allocation regardless of other scores.',
    usedIn: 'Applied as a Linear Allocation eligibility rule before final target normalization.',
    example: 'If scenario expected value is below the current price, the row receives a zero target when this is enabled.',
    tuning: 'Usually keep enabled. It prevents the model from allocating to stocks where scenario expected value is below the current price.',
    related: ['Linear min upside %', 'Linear Score'],
  });

  addConfigHelp('linear_max_single_stock_pct', {
    title: 'Linear max single-stock %',
    meaning: 'Maximum target allocation allowed for any single stock in the Linear Allocation model.',
    usedIn: 'Applied as a cap after preliminary linear target weights are calculated.',
    formula: 'Linear Target Mid After Caps = min(preliminary target, applicable linear caps)',
    example: 'If an uncapped stock target is 12% and this cap is 10%, the final linear target mid is capped at 10% before redistribution.',
    tuning: 'Use this as the main concentration control. Around 8% to 10% is reasonable for a concentrated portfolio; lower values create more diversification.',
    related: ['Linear risk caps', 'Linear allocated target total %'],
  });

  addConfigHelp('linear_add_band_tolerance_pct', {
    title: 'Linear add band tolerance %',
    meaning: 'Tolerance below Linear Target Mid before an underweight position becomes an Add candidate.',
    usedIn: 'Used to calculate the lower side of the Linear Target Band.',
    formula: 'Target Low = Linear Target Mid × (1 - Add Band Tolerance %)',
    example: 'If Target Mid is 4% and add tolerance is 15%, the lower band is 3.4%. Below that, the position can become an Add candidate.',
    tuning: 'Lower values create add signals sooner. Higher values require a larger underweight gap before adding. A reasonable default is 15%.',
    related: ['Linear Target Mid', 'Linear trim band tolerance %', 'Gap to Mid'],
  });

  addConfigHelp('linear_trim_band_tolerance_pct', {
    title: 'Linear trim band tolerance %',
    meaning: 'Tolerance above Linear Target Mid before an overweight position becomes a Trim candidate.',
    usedIn: 'Used to calculate the upper side of the Linear Target Band.',
    formula: 'Target High = Linear Target Mid × (1 + Trim Band Tolerance %)',
    example: 'If Target Mid is 4% and trim tolerance is 30%, the upper band is 5.2%. Above that, the position can become a Trim candidate.',
    tuning: 'Use a higher trim tolerance than add tolerance if you want to avoid trimming strong long-term winners too aggressively. A reasonable default is 30%.',
    related: ['Linear Target Mid', 'Linear add band tolerance %', 'Trim actions'],
  });

  addConfigHelp('linear_target_band_tolerance_pct', {
    title: 'Linear target band tolerance % (legacy)',
    meaning: 'Legacy single target-band tolerance kept for saved-setting compatibility.',
    usedIn: 'Used only as a fallback when the newer linear add and trim band tolerance settings are missing from saved settings.',
    tuning: 'Prefer using Linear add band tolerance % and Linear trim band tolerance % for new configurations.',
    related: ['Linear add band tolerance %', 'Linear trim band tolerance %'],
  });

  addConfigHelp('linear_enable_risk_caps', {
    title: 'Enable linear risk caps',
    meaning: 'Turns Linear Allocation-specific risk caps on or off.',
    usedIn: 'When enabled, additional caps can reduce target weights for stocks with negative or weak confidence characteristics.',
    example: 'A high-upside stock with negative Core Net can be capped at the negative-core cap instead of receiving the full score-based target.',
    tuning: 'Usually keep enabled. It helps prevent high-upside but weak-confidence stocks from receiving too much allocation.',
    related: ['Linear negative core net cap %', 'Linear low core net cap %', 'Linear high bearish confidence cap %'],
  });

  addConfigHelp('linear_negative_core_net_cap_pct', {
    title: 'Linear negative core net cap %',
    meaning: 'Maximum target allocation allowed for stocks with negative Core Net confidence.',
    usedIn: 'Applied when Core Net confidence is below 0 and linear risk caps are enabled.',
    example: 'If this cap is 2%, a stock with Core Net below 0 cannot receive a Linear Target Mid above 2% from this model.',
    tuning: 'Use this to heavily limit companies where core business drivers are net negative. A reasonable default is around 2%.',
    related: ['Enable linear risk caps', 'Linear min core net'],
  });

  addConfigHelp('linear_low_core_net_threshold', {
    title: 'Linear low core net threshold',
    meaning: 'Core Net confidence level below which a stock is considered low-confidence for linear risk-cap purposes.',
    usedIn: 'If Core Net is below this threshold, but not necessarily negative, the low-core cap may apply when risk caps are enabled.',
    example: 'With a threshold of 0.5, a stock with Core Net 0.2 is treated as low-core-confidence for cap logic.',
    tuning: 'A reasonable default is 0.5. Raise it to make the model more conservative; lower it to let more companies avoid the low-core cap.',
    related: ['Linear low core net cap %', 'Enable linear risk caps'],
  });

  addConfigHelp('linear_low_core_net_cap_pct', {
    title: 'Linear low core net cap %',
    meaning: 'Maximum target allocation allowed for stocks with Core Net confidence below the low-core threshold.',
    usedIn: 'Applied when Core Net is below linear_low_core_net_threshold and linear risk caps are enabled.',
    example: 'If the threshold is 0.5 and this cap is 4%, a stock with Core Net 0.2 is capped at 4%.',
    tuning: 'Use this to limit companies with weak but not necessarily negative core confidence. A reasonable default is around 4%.',
    related: ['Linear low core net threshold', 'Enable linear risk caps'],
  });

  addConfigHelp('linear_high_bearish_confidence_min_threshold', {
    title: 'Linear high bearish confidence min threshold',
    meaning: 'Raw bearish-confidence score at or below which no bearish allocation cap is applied.',
    usedIn: 'Starts progressive high-bearish-confidence capping. This is a raw confidence score, not a percentage.',
    example: 'With a minimum of 4 and maximum of 8, Core Bearish Confidence 4 applies 0% of the cap.',
    tuning: 'Raise this value to delay when progressive capping begins. It must remain below the maximum threshold.',
    related: ['Linear high bearish confidence max threshold', 'Linear high bearish confidence cap %', 'Enable linear risk caps'],
  });

  addConfigHelp('linear_high_bearish_confidence_max_threshold', {
    title: 'Linear high bearish confidence max threshold',
    meaning: 'Raw bearish-confidence score at or above which the full bearish allocation cap is applied.',
    usedIn: 'Ends progressive high-bearish-confidence capping. This is a raw confidence score, not a percentage.',
    example: 'With a minimum of 4 and maximum of 8, Core Bearish Confidence 8 applies 100% of the cap.',
    tuning: 'Lower this value to reach the full cap sooner. It must remain above the minimum threshold.',
    related: ['Linear high bearish confidence min threshold', 'Linear high bearish confidence cap %', 'Enable linear risk caps'],
  });

  addConfigHelp('linear_high_bearish_confidence_cap_pct', {
    title: 'Linear high bearish confidence cap %',
    meaning: 'Maximum Target Band midpoint allowed when the bearish-confidence cap is fully applied.',
    usedIn: 'The allocation percentage approached progressively between the raw minimum and maximum confidence thresholds.',
    example: 'If this cap is 5%, a 10% uncapped midpoint is progressively reduced toward 5% as bearish confidence rises.',
    tuning: 'Use this to prevent overallocating to stocks with strong upside but unusually strong downside variables. A reasonable default is around 5%.',
    related: ['Linear high bearish confidence min threshold', 'Linear high bearish confidence max threshold', 'Enable linear risk caps'],
  });

}

registerActionPlanConfigHelp();

let savedGeneralSettings = null;

const POSITIONS_CACHE_KEY = 'bakingmoney.latestPositions';

const RATING_FILTER_OPTIONS = [
  { key: 'strong_buy', label: 'Strong Buy' },
  { key: 'buy', label: 'Buy' },
  { key: 'speculative_buy', label: 'Speculative Buy' },
  { key: 'hold', label: 'Hold' },
  { key: 'sell', label: 'Sell' },
  { key: 'strong_sell', label: 'Strong Sell' },
];

const RATING_FILTER_LABEL_BY_KEY = Object.fromEntries(RATING_FILTER_OPTIONS.map((option) => [option.key, option.label]));

const ACTION_PLAN_ACTION_FILTER_OPTIONS = [
  { key: 'add', label: 'Add' },
  { key: 'trim', label: 'Trim' },
  { key: 'sell', label: 'Sell' },
  { key: 'watch', label: 'Watch' },
  { key: 'hold', label: 'Hold' },
  { key: 'watch_extended', label: 'Watch / Extended' },
  { key: 'watch_rating_guardrail', label: 'Watch / Rating Guardrail' },
];

const ACTION_PLAN_ACTION_FILTER_LABEL_BY_KEY = Object.fromEntries(
  ACTION_PLAN_ACTION_FILTER_OPTIONS.map((option) => [option.key, option.label])
);

const ACTION_PLAN_ACTION_FILTER_KEY_BY_LABEL = Object.fromEntries(
  ACTION_PLAN_ACTION_FILTER_OPTIONS.map((option) => [option.label, option.key])
);

function getActionPlanActionFilterKey(actionLabel) {
  const label = String(actionLabel || '');
  if (label === 'Watch / Extended') return 'watch_extended';
  if (label === 'Watch / Rating Guardrail') return 'watch_rating_guardrail';
  if (label === 'Watch') return 'watch';
  if (label.startsWith('Hold')) return 'hold';
  return ACTION_PLAN_ACTION_FILTER_KEY_BY_LABEL[label];
}

const EARNINGS_CALENDAR_DATE_FILTER_OPTIONS = [
  { key: 'past', label: 'Past' },
  { key: 'yesterday', label: 'Yesterday' },
  { key: 'today', label: 'Today' },
  { key: 'tomorrow', label: 'Tomorrow' },
  { key: 'current_week', label: 'Current Week' },
  { key: 'next_week', label: 'Next Week' },
  { key: 'future', label: 'Future' },
];

const EARNINGS_CALENDAR_DATE_FILTER_LABEL_BY_KEY = Object.fromEntries(
  EARNINGS_CALENDAR_DATE_FILTER_OPTIONS.map((option) => [option.key, option.label])
);

const EARNINGS_CALENDAR_QUARTER_FILTER_OPTIONS = ['Q1', 'Q2', 'Q3', 'Q4'];

function getAllRatingFilterKeys() {
  return new Set(RATING_FILTER_OPTIONS.map((option) => option.key));
}

function getAllActionPlanActionFilterKeys() {
  return new Set(ACTION_PLAN_ACTION_FILTER_OPTIONS.map((option) => option.key));
}

function getAllEarningsCalendarDateFilterKeys() {
  return new Set(EARNINGS_CALENDAR_DATE_FILTER_OPTIONS.map((option) => option.key));
}

function getAllEarningsCalendarFiscalYearKeys() {
  return new Set(getAvailableEarningsCalendarFiscalYears());
}

function getAllEarningsCalendarFiscalQuarterKeys() {
  return new Set(EARNINGS_CALENDAR_QUARTER_FILTER_OPTIONS);
}

function getCurrentCalendarYear() {
  return new Date().getFullYear();
}

function getCurrentCalendarQuarter() {
  const month = new Date().getMonth();
  const quarter = Math.floor(month / 3) + 1;
  return `Q${quarter}`;
}

function resetEarningsCalendarAddFormDefaults() {
  if (earningsCalendarAddFiscalYearEl) {
    earningsCalendarAddFiscalYearEl.value = String(getCurrentCalendarYear());
  }
  if (earningsCalendarAddFiscalQuarterEl) {
    earningsCalendarAddFiscalQuarterEl.value = getCurrentCalendarQuarter();
  }
  earningsCalendarAddFormDefaultsApplied = true;
}

function applyEarningsCalendarEntryDefaults({ force = false } = {}) {
  if (force || !earningsCalendarAddFormDefaultsApplied) {
    resetEarningsCalendarAddFormDefaults();
    return;
  }
  if (earningsCalendarAddFiscalYearEl && !String(earningsCalendarAddFiscalYearEl.value || '').trim()) {
    earningsCalendarAddFiscalYearEl.value = String(getCurrentCalendarYear());
  }
  if (earningsCalendarAddFiscalQuarterEl && !earningsCalendarAddFiscalQuarterEl.value) {
    earningsCalendarAddFiscalQuarterEl.value = getCurrentCalendarQuarter();
  }
}

function setSelectedRatings(keys) {
  ratingFilters = new Set(keys);
  if (analysisRatingFilterPanelEl) {
    analysisRatingFilterPanelEl.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
      checkbox.checked = ratingFilters.has(checkbox.value);
    });
  }
  updateRatingFilterLabel();
}

function setSelectedPositionRatings(keys) {
  positionRatingFilters = new Set(keys);
  if (positionsRatingFilterPanelEl) {
    positionsRatingFilterPanelEl.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
      checkbox.checked = positionRatingFilters.has(checkbox.value);
    });
  }
  updatePositionRatingFilterLabel();
}

function setSelectedActionPlanRatings(keys) {
  actionPlanRatingFilters = new Set(keys);
  if (actionPlanRatingFilterPanelEl) {
    actionPlanRatingFilterPanelEl.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
      checkbox.checked = actionPlanRatingFilters.has(checkbox.value);
    });
  }
  updateActionPlanRatingFilterLabel();
}

function setSelectedActionPlanActions(keys) {
  actionPlanActionFilters = new Set(keys);
  if (actionPlanActionFilterPanelEl) {
    actionPlanActionFilterPanelEl.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
      checkbox.checked = actionPlanActionFilters.has(checkbox.value);
    });
  }
  updateActionPlanActionFilterLabel();
}

function setSelectedEarningsCalendarDateFilters(keys) {
  earningsCalendarDateFilters = new Set(keys);
  if (earningsCalendarDateFilterPanelEl) {
    earningsCalendarDateFilterPanelEl.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
      checkbox.checked = earningsCalendarDateFilters.has(checkbox.value);
    });
  }
  updateEarningsCalendarDateFilterLabel();
}

function setSelectedEarningsCalendarFiscalYears(keys) {
  earningsCalendarFiscalYearFilters = new Set(Array.from(keys || []).map(String));
  if (earningsCalendarFiscalYearFilterPanelEl) {
    earningsCalendarFiscalYearFilterPanelEl.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
      checkbox.checked = earningsCalendarFiscalYearFilters.has(checkbox.value);
    });
  }
  updateEarningsCalendarFiscalYearFilterLabel();
}

function setSelectedEarningsCalendarFiscalQuarters(keys) {
  earningsCalendarFiscalQuarterFilters = new Set(keys || []);
  if (earningsCalendarFiscalQuarterFilterPanelEl) {
    earningsCalendarFiscalQuarterFilterPanelEl.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
      checkbox.checked = earningsCalendarFiscalQuarterFilters.has(checkbox.value);
    });
  }
  updateEarningsCalendarFiscalQuarterFilterLabel();
}

function getAvailableEarningsCalendarFiscalYears() {
  return Array.from(new Set(earningsCalendarItems
    .map((item) => item?.fiscal_year)
    .filter((year) => year !== null && year !== undefined && String(year).trim() !== '')
    .map((year) => String(year))))
    .sort((a, b) => Number(b) - Number(a));
}

function syncEarningsCalendarFiscalYearFilterOptions() {
  const years = getAvailableEarningsCalendarFiscalYears();
  const available = new Set(years);
  const preserved = Array.from(earningsCalendarFiscalYearFilters).filter((year) => available.has(year));
  earningsCalendarFiscalYearFilters = new Set(preserved);
  if (earningsCalendarFiscalYearFilterOptionsEl) {
    earningsCalendarFiscalYearFilterOptionsEl.innerHTML = years.map((year) => `<label class="rating-filter-option"><input type="checkbox" value="${escapeHtml(year)}" ${earningsCalendarFiscalYearFilters.has(year) ? 'checked' : ''} /> <span class="rating-filter-option-label">${escapeHtml(year)}</span></label>`).join('') || '<p class="muted small-text">No fiscal years</p>';
  }
  updateEarningsCalendarFiscalYearFilterLabel();
}

function getSelectedRatings() {
  return new Set(ratingFilters);
}

function getSelectedPositionRatings() {
  return new Set(positionRatingFilters);
}

function getSelectedActionPlanRatings() {
  return new Set(actionPlanRatingFilters);
}

function getSelectedActionPlanActions() {
  return new Set(actionPlanActionFilters);
}

function getSelectedEarningsCalendarDateFilters() {
  return new Set(earningsCalendarDateFilters);
}

function getSelectedEarningsCalendarFiscalYears() {
  return new Set(earningsCalendarFiscalYearFilters);
}

function getSelectedEarningsCalendarFiscalQuarters() {
  return new Set(earningsCalendarFiscalQuarterFilters);
}

function updateRatingFilterLabel() {
  const selected = Array.from(getSelectedRatings());
  const totalCount = RATING_FILTER_OPTIONS.length;
  const selectedCount = selected.length;

  if (!analysisRatingFilterLabelEl) return;

  if (selectedCount === 0 || selectedCount === totalCount) {
    analysisRatingFilterLabelEl.textContent = 'All';
    return;
  }

  if (selectedCount === 1) {
    analysisRatingFilterLabelEl.textContent = RATING_FILTER_LABEL_BY_KEY[selected[0]] || 'All';
    return;
  }

  analysisRatingFilterLabelEl.textContent = `${selectedCount} selected`;
}

function updatePositionRatingFilterLabel() {
  const selected = Array.from(getSelectedPositionRatings());
  const totalCount = RATING_FILTER_OPTIONS.length;
  const selectedCount = selected.length;

  if (!positionsRatingFilterLabelEl) return;

  if (selectedCount === 0 || selectedCount === totalCount) {
    positionsRatingFilterLabelEl.textContent = 'All';
    return;
  }

  if (selectedCount === 1) {
    positionsRatingFilterLabelEl.textContent = RATING_FILTER_LABEL_BY_KEY[selected[0]] || 'All';
    return;
  }

  positionsRatingFilterLabelEl.textContent = `${selectedCount} selected`;
}

function updateActionPlanRatingFilterLabel() {
  const selected = Array.from(getSelectedActionPlanRatings());
  const totalCount = RATING_FILTER_OPTIONS.length;
  const selectedCount = selected.length;

  if (!actionPlanRatingFilterLabelEl) return;

  if (selectedCount === 0 || selectedCount === totalCount) {
    actionPlanRatingFilterLabelEl.textContent = 'All';
    return;
  }

  if (selectedCount === 1) {
    actionPlanRatingFilterLabelEl.textContent = RATING_FILTER_LABEL_BY_KEY[selected[0]] || 'All';
    return;
  }

  actionPlanRatingFilterLabelEl.textContent = `${selectedCount} selected`;
}

function updateActionPlanActionFilterLabel() {
  const selected = Array.from(getSelectedActionPlanActions());
  const totalCount = ACTION_PLAN_ACTION_FILTER_OPTIONS.length;
  const selectedCount = selected.length;

  if (!actionPlanActionFilterLabelEl) return;

  if (selectedCount === 0 || selectedCount === totalCount) {
    actionPlanActionFilterLabelEl.textContent = 'All';
    return;
  }

  if (selectedCount === 1) {
    actionPlanActionFilterLabelEl.textContent = ACTION_PLAN_ACTION_FILTER_LABEL_BY_KEY[selected[0]] || 'All';
    return;
  }

  actionPlanActionFilterLabelEl.textContent = `${selectedCount} selected`;
}

function updateEarningsCalendarDateFilterLabel() {
  const selected = Array.from(getSelectedEarningsCalendarDateFilters());
  const selectedCount = selected.length;

  if (!earningsCalendarDateFilterLabelEl) return;

  const totalCount = EARNINGS_CALENDAR_DATE_FILTER_OPTIONS.length;

  if (selectedCount === 0 || selectedCount === totalCount) {
    earningsCalendarDateFilterLabelEl.textContent = 'All';
    return;
  }

  if (selectedCount === 1) {
    earningsCalendarDateFilterLabelEl.textContent = EARNINGS_CALENDAR_DATE_FILTER_LABEL_BY_KEY[selected[0]] || 'All';
    return;
  }

  earningsCalendarDateFilterLabelEl.textContent = `${selectedCount} selected`;
}

function updateEarningsCalendarFiscalYearFilterLabel() {
  const selected = Array.from(getSelectedEarningsCalendarFiscalYears());
  const selectedCount = selected.length;
  const totalCount = getAvailableEarningsCalendarFiscalYears().length;
  if (!earningsCalendarFiscalYearFilterLabelEl) return;
  if (selectedCount === 0 || selectedCount === totalCount) {
    earningsCalendarFiscalYearFilterLabelEl.textContent = 'All';
    return;
  }
  earningsCalendarFiscalYearFilterLabelEl.textContent = selectedCount === 1 ? selected[0] : `${selectedCount} selected`;
}

function updateEarningsCalendarFiscalQuarterFilterLabel() {
  const selected = Array.from(getSelectedEarningsCalendarFiscalQuarters());
  const selectedCount = selected.length;
  const totalCount = EARNINGS_CALENDAR_QUARTER_FILTER_OPTIONS.length;
  if (!earningsCalendarFiscalQuarterFilterLabelEl) return;
  if (selectedCount === 0 || selectedCount === totalCount) {
    earningsCalendarFiscalQuarterFilterLabelEl.textContent = 'All';
    return;
  }
  earningsCalendarFiscalQuarterFilterLabelEl.textContent = selectedCount === 1 ? selected[0] : `${selectedCount} selected`;
}

const FLOATING_FILTER_MARGIN = 8;

function resetFloatingFilterPanel(panel) {
  if (!panel) return;
  panel.classList.remove('is-floating');
  panel.style.left = '';
  panel.style.right = '';
  panel.style.top = '';
  panel.style.width = '';
  panel.style.minWidth = '';
  panel.style.maxHeight = '';
}

function positionFloatingFilterPanel(toggle, panel) {
  if (!toggle || !panel || panel.classList.contains('hidden')) return;
  const rect = toggle.getBoundingClientRect();
  const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
  const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
  const maxPanelWidth = Math.max(160, viewportWidth - FLOATING_FILTER_MARGIN * 2);
  const preferredWidth = Math.min(
    maxPanelWidth,
    Math.max(rect.width, panel.scrollWidth || panel.offsetWidth || 236, 236)
  );
  const left = Math.min(
    Math.max(FLOATING_FILTER_MARGIN, rect.left),
    Math.max(FLOATING_FILTER_MARGIN, viewportWidth - preferredWidth - FLOATING_FILTER_MARGIN)
  );
  const availableBelow = Math.max(0, viewportHeight - rect.bottom - FLOATING_FILTER_MARGIN);
  const availableAbove = Math.max(0, rect.top - FLOATING_FILTER_MARGIN);
  const desiredHeight = Math.min(panel.scrollHeight || 400, 400);
  const openUpward = availableBelow < desiredHeight && availableAbove > availableBelow;
  const availableHeight = Math.max(120, (openUpward ? availableAbove : availableBelow) - 6);
  const maxHeight = Math.min(400, availableHeight);
  panel.classList.add('is-floating');
  panel.style.width = `${preferredWidth}px`;
  panel.style.minWidth = `${preferredWidth}px`;
  panel.style.maxHeight = `${maxHeight}px`;
  panel.style.left = `${left}px`;
  panel.style.right = 'auto';
  if (openUpward) {
    const actualHeight = Math.min(panel.scrollHeight || maxHeight, maxHeight);
    panel.style.top = `${Math.max(FLOATING_FILTER_MARGIN, rect.top - actualHeight - 6)}px`;
  } else {
    panel.style.top = `${Math.min(rect.bottom + 6, Math.max(FLOATING_FILTER_MARGIN, viewportHeight - maxHeight - FLOATING_FILTER_MARGIN))}px`;
  }
}

function setFloatingFilterOpen(filterEl, panelEl, toggleEl, isOpen) {
  if (!filterEl || !panelEl || !toggleEl) return;
  filterEl.dataset.open = isOpen ? 'true' : 'false';
  panelEl.classList.toggle('hidden', !isOpen);
  toggleEl.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  if (isOpen) positionFloatingFilterPanel(toggleEl, panelEl);
  else resetFloatingFilterPanel(panelEl);
}

function repositionOpenFloatingFilters() {
  [
    [analysisRatingFilterEl, analysisRatingFilterPanelEl, analysisRatingFilterToggleEl],
    [positionsRatingFilterEl, positionsRatingFilterPanelEl, positionsRatingFilterToggleEl],
    [actionPlanRatingFilterEl, actionPlanRatingFilterPanelEl, actionPlanRatingFilterToggleEl],
    [actionPlanActionFilterEl, actionPlanActionFilterPanelEl, actionPlanActionFilterToggleEl],
    [earningsCalendarDateFilterEl, earningsCalendarDateFilterPanelEl, earningsCalendarDateFilterToggleEl],
    [earningsCalendarFiscalYearFilterEl, earningsCalendarFiscalYearFilterPanelEl, earningsCalendarFiscalYearFilterToggleEl],
    [earningsCalendarFiscalQuarterFilterEl, earningsCalendarFiscalQuarterFilterPanelEl, earningsCalendarFiscalQuarterFilterToggleEl],
  ].forEach(([filterEl, panelEl, toggleEl]) => {
    if (filterEl?.dataset.open === 'true') positionFloatingFilterPanel(toggleEl, panelEl);
  });
}

function setRatingFilterOpen(isOpen) {
  setFloatingFilterOpen(analysisRatingFilterEl, analysisRatingFilterPanelEl, analysisRatingFilterToggleEl, isOpen);
}

function setPositionsRatingFilterOpen(isOpen) {
  setFloatingFilterOpen(positionsRatingFilterEl, positionsRatingFilterPanelEl, positionsRatingFilterToggleEl, isOpen);
}

function setActionPlanRatingFilterOpen(isOpen) {
  setFloatingFilterOpen(actionPlanRatingFilterEl, actionPlanRatingFilterPanelEl, actionPlanRatingFilterToggleEl, isOpen);
}

function setActionPlanActionFilterOpen(isOpen) {
  setFloatingFilterOpen(actionPlanActionFilterEl, actionPlanActionFilterPanelEl, actionPlanActionFilterToggleEl, isOpen);
}

function setEarningsCalendarDateFilterOpen(isOpen) {
  setFloatingFilterOpen(earningsCalendarDateFilterEl, earningsCalendarDateFilterPanelEl, earningsCalendarDateFilterToggleEl, isOpen);
}

function setEarningsCalendarFiscalYearFilterOpen(isOpen) {
  setFloatingFilterOpen(earningsCalendarFiscalYearFilterEl, earningsCalendarFiscalYearFilterPanelEl, earningsCalendarFiscalYearFilterToggleEl, isOpen);
}

function setEarningsCalendarFiscalQuarterFilterOpen(isOpen) {
  setFloatingFilterOpen(earningsCalendarFiscalQuarterFilterEl, earningsCalendarFiscalQuarterFilterPanelEl, earningsCalendarFiscalQuarterFilterToggleEl, isOpen);
}

function loadCachedPositions() {
  try {
    const raw = localStorage.getItem(POSITIONS_CACHE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((item) => Math.abs(Number(item?.position) || 0) > 0) : [];
  } catch (_error) {
    return [];
  }
}

function saveCachedPositions(positions) {
  try {
    const activeOnly = Array.isArray(positions)
      ? positions.filter((item) => Math.abs(Number(item?.position) || 0) > 0)
      : [];
    localStorage.setItem(POSITIONS_CACHE_KEY, JSON.stringify(activeOnly));
  } catch (_error) {
    // Ignore localStorage write failures.
  }
}

latestPositions = loadCachedPositions();

async function getScenarioPassCountForStatus() {
  try {
    const response = await fetch('/api/configuration/general');
    const payload = await response.json();
    if (!response.ok) return 1;
    const settings = payload.settings || {};
    if (!settings.scenario_multi_pass_enabled) return 1;
    const count = Number(settings.scenario_pass_count || 1);
    return Number.isFinite(count) && count > 1 ? Math.floor(count) : 1;
  } catch (_error) {
    return 1;
  }
}

function buildScenarioStatusMessage(symbol, passCount) {
  const suffix = passCount > 1 ? ` (multi-pass: ${passCount})` : '';
  return `Building scenarios for ${symbol}${suffix}…`;
}

function extractErrorMessage(payload, fallback) {
  if (!payload || typeof payload !== 'object') return fallback;
  return [payload.error, payload.details, payload.debugHint].filter(Boolean).join(' ') || fallback;
}

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function formatSkippedPriceSymbols(skippedSymbols) {
  const items = Array.isArray(skippedSymbols) ? skippedSymbols.filter((item) => item && item.symbol) : [];
  if (!items.length) return '';
  const symbols = items.map((item) => item.symbol);
  if (symbols.length <= 4) return symbols.join(', ');
  return `${symbols.slice(0, 4).join(', ')}, and ${symbols.length - 4} more`;
}

function logSkippedPriceDetails(skippedSymbols) {
  const items = Array.isArray(skippedSymbols) ? skippedSymbols : [];
  items.forEach((item) => {
    if (!item?.symbol) return;
    console.warn(`${item.symbol} skipped: ${item.reason || 'No valid market price returned before timeout'}.`, item);
  });
}

function logFallbackPriceDetails(fallbackSymbols, keptPreviousSymbols) {
  (Array.isArray(fallbackSymbols) ? fallbackSymbols : []).forEach((item) => {
    if (!item?.symbol) return;
    console.info(`${item.symbol} price fallback: ${item.source || 'fallback'}${item.warning ? ` (${item.warning})` : ''}.`, item);
  });
  (Array.isArray(keptPreviousSymbols) ? keptPreviousSymbols : []).forEach((item) => {
    if (!item?.symbol) return;
    console.warn(`${item.symbol} kept previous price: ${item.warning || 'All refresh sources failed.'}`, item);
  });
}

function shouldRetryTwsPositionsRefresh(payload) {
  if (!payload || typeof payload !== 'object') return false;
  if (payload.data_source && payload.data_source !== 'live') return true;
  const warning = String(payload.warning || '');
  return /TWS offline|TWS unavailable|no saved positions/i.test(warning);
}

function shouldRetryTwsAnalysisPriceRefresh(payload) {
  if (!payload || typeof payload !== 'object') return false;
  return Number(payload.updated || 0) === 0 && Number(payload.skipped || 0) > 0;
}
const formatNumber = (value, digits = 2) => (typeof value !== 'number' || Number.isNaN(value) ? 'N/A' : value.toLocaleString(undefined, { maximumFractionDigits: digits }));
const formatCurrencyValue = (value, currency, digits = 2) => {
  const formatted = formatNumber(value, digits);
  return !currency || formatted === 'N/A' ? formatted : `${formatted} ${currency}`;
};
const formatPercent = (value) => (typeof value !== 'number' || Number.isNaN(value) ? 'N/A' : `${value.toFixed(2)}%`);
const valueClass = (value) => (typeof value !== 'number' || Number.isNaN(value) || value === 0 ? '' : value > 0 ? 'pnl-positive' : 'pnl-negative');
const formatConfidencePair = (bullish, bearish) => `${formatNumber(bullish, 2)} / ${formatNumber(bearish, 2)}`;
const isFiniteNumber = (value) => typeof value === 'number' && Number.isFinite(value);
const formatConfidenceDiffDisplay = (diff, bullish, bearish) => {
  if (!isFiniteNumber(bullish) || !isFiniteNumber(bearish)) return 'N/A';
  const diffNumber = isFiniteNumber(diff) ? diff : bullish - bearish;
  const diffText = `${diffNumber >= 0 ? '+' : ''}${diffNumber.toFixed(2)}`;
  return `${diffText} (${formatNumber(bullish, 2)} / ${formatNumber(bearish, 2)})`;
};
const getCoreConfidenceFields = (item) => {
  const hasCore = isFiniteNumber(item?.core_bullish_confidence) && isFiniteNumber(item?.core_bearish_confidence);
  return hasCore
    ? {
        diff: item.core_confidence_diff,
        bullish: item.core_bullish_confidence,
        bearish: item.core_bearish_confidence,
      }
    : {
        diff: item?.confidence_diff,
        bullish: item?.bullish_confidence,
        bearish: item?.bearish_confidence,
      };
};
const formatCoreConfidenceDisplay = (item) => {
  const fields = getCoreConfidenceFields(item);
  return formatConfidenceDiffDisplay(fields.diff, fields.bullish, fields.bearish);
};
const formatPotentialConfidenceDisplay = (item) => formatConfidenceDiffDisplay(
  item?.potential_confidence_diff,
  item?.potential_bullish_confidence,
  item?.potential_bearish_confidence,
);
function parseDateValue(value) {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}
function formatDate(value) {
  const d = parseDateValue(value);
  if (!d) return 'N/A';
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  return `${day}.${month}.${year}`;
}
function getLinearReleaseDateParts(value) {
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  const year = Number(match[1]); const month = Number(match[2]); const day = Number(match[3]);
  const timestamp = Date.UTC(year, month - 1, day);
  return Number.isFinite(timestamp) && month >= 1 && month <= 12 && day >= 1 && day <= 31 ? { year, month, day, timestamp } : null;
}
function formatLinearReleaseDate(item) {
  const parts = getLinearReleaseDateParts(item?.release_date);
  if (!parts) return '—';
  const month = new Intl.DateTimeFormat(undefined, { month: 'short', timeZone: 'UTC' }).format(new Date(parts.timestamp));
  const currentYear = new Date().getFullYear();
  const timing = item?.release_timing === 'Before Open' ? ' BMO' : (item?.release_timing === 'After Close' ? ' AMC' : '');
  return `${month} ${parts.day}${parts.year === currentYear ? '' : `, ${parts.year}`}${timing}`;
}
function getLinearReleaseDateSortValue(item) {
  const parts = getLinearReleaseDateParts(item?.release_date);
  if (!parts) return null;
  const today = new Date();
  const todayTimestamp = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  return parts.timestamp >= todayTimestamp ? parts.timestamp : 10000000000000000 + parts.timestamp;
}
function getLinearReleaseDateWarning(item) {
  if (item?.release_date_warning !== true) return null;
  const daysUntil = Number(item.release_date_days_until);
  const warningDays = Number(item.release_date_warning_days);
  if (!Number.isInteger(daysUntil) || daysUntil < 0 || !Number.isInteger(warningDays) || warningDays <= 0) return null;
  const timeLabel = daysUntil === 0 ? 'is today' : `is in ${daysUntil} day${daysUntil === 1 ? '' : 's'}`;
  const timingLabel = item.release_timing === 'Before Open' || item.release_timing === 'After Close' ? `, ${item.release_timing}` : '';
  const message = `Release date ${timeLabel}${timingLabel}. Consider waiting for results before executing.`;
  return {
    message,
    ariaLabel: `Release date is within ${warningDays} days for ${item.symbol || 'this stock'}. ${message}`,
  };
}
function renderLinearReleaseDateWarning(item) {
  const warning = getLinearReleaseDateWarning(item);
  if (!warning) return '';
  return `<span class="release-date-warning-icon" role="img" tabindex="0" title="${escapeHtml(warning.message)}" aria-label="${escapeHtml(warning.ariaLabel)}">⚠</span>`;
}
function formatLinearMomentum(item) {
  const score = Number(item?.momentum_score);
  return Number.isFinite(score) ? `${score.toFixed(1)}${item?.momentum_label ? ` ${item.momentum_label}` : ''}` : '—';
}
function formatLocalDateForExternalScenarioNotes(dateValue = new Date()) {
  const day = String(dateValue.getDate()).padStart(2, '0');
  const month = String(dateValue.getMonth() + 1).padStart(2, '0');
  const year = dateValue.getFullYear();
  return `${day}.${month}.${year}`;
}
const formatDateTime = (v) => {
  const d = parseDateValue(v);
  if (!d) return 'N/A';
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  return `${day}.${month}.${year} ${hours}:${minutes}`;
};

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function getConfigFieldLabel(labelEl, controlEl) {
  const clone = labelEl.cloneNode(true);
  clone.querySelectorAll('input, select, textarea, button, small').forEach((node) => node.remove());
  const text = clone.textContent.trim().replace(/\s+/g, ' ');
  if (text) return text;
  return controlEl?.id?.replace(/^config-/, '').replace(/-/g, ' ') || 'Configuration parameter';
}

function getConfigHelpKey(controlEl) {
  return controlEl?.dataset?.actionPlanSetting || controlEl?.id?.replace(/^config-/, '').replace(/-/g, '_') || '';
}

function getConfigHelpContent(key, label) {
  return CONFIG_HELP[key] || {
    title: label || key || 'Configuration parameter',
    meaning: 'No detailed explanation is available yet.',
    usedIn: 'This parameter is shown on the Configuration page and is saved with the rest of the app settings.',
    tuning: 'Use the default unless you have a specific reason to tune this setting.',
  };
}

function renderConfigHelpSections(help) {
  const sections = [
    ['Meaning', help.meaning],
    ['Where used', help.usedIn],
    ['Formula / impact', help.formula, 'pre'],
    ['Example', help.example, 'pre'],
    ['Tuning guidance', help.tuning],
  ].filter(([, value]) => value);
  const related = Array.isArray(help.related) && help.related.length
    ? `<section class="config-help-section"><h4>Related parameters</h4><div class="config-help-related">${help.related.map((item) => `<span>${escapeHtml(item)}</span>`).join('')}</div></section>`
    : '';
  return `${sections.map(([title, value, type]) => `<section class="config-help-section"><h4>${escapeHtml(title)}</h4>${type === 'pre' ? `<pre>${escapeHtml(value)}</pre>` : `<p>${escapeHtml(value)}</p>`}</section>`).join('')}${related}`;
}

function openConfigHelpModal(key, label, triggerEl) {
  if (!configHelpModalEl || !configHelpTitleEl || !configHelpContentEl) return;
  const help = getConfigHelpContent(key, label);
  lastConfigHelpTrigger = triggerEl || null;
  configHelpTitleEl.textContent = help.title || label || 'Configuration Help';
  configHelpContentEl.innerHTML = renderConfigHelpSections(help);
  configHelpModalEl.classList.remove('hidden');
  configHelpCloseBtn?.focus();
}

function closeConfigHelpModal() {
  if (!configHelpModalEl) return;
  configHelpModalEl.classList.add('hidden');
  if (lastConfigHelpTrigger && typeof lastConfigHelpTrigger.focus === 'function') {
    lastConfigHelpTrigger.focus();
  }
  lastConfigHelpTrigger = null;
}

function initializeConfigHelpIcons() {
  document.querySelectorAll('#configuration label').forEach((labelEl) => {
    const controlEl = labelEl.querySelector('input, select, textarea');
    if (!controlEl || labelEl.querySelector('.config-help-button')) return;
    const key = getConfigHelpKey(controlEl);
    const label = getConfigFieldLabel(labelEl, controlEl);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'config-help-button';
    button.dataset.configHelpKey = key;
    button.dataset.configHelpLabel = label;
    button.setAttribute('aria-label', `Show help for ${label}`);
    button.textContent = 'i';
    button.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      openConfigHelpModal(key, label, button);
    });
    const small = labelEl.querySelector('small');
    labelEl.insertBefore(button, small || null);
  });
}

function normalizeDriverCategory(value) {
  return value === 'Potential Driver' ? 'Potential Driver' : 'Core Driver';
}

function renderDriverCategorySelect(className, value) {
  const category = normalizeDriverCategory(value);
  return `<select class="${className}"><option value="Core Driver" ${category === 'Core Driver' ? 'selected' : ''}>Core Driver</option><option value="Potential Driver" ${category === 'Potential Driver' ? 'selected' : ''}>Potential Driver</option></select>`;
}

function normalizeSymbolForJoin(symbol) {
  return String(symbol ?? '').trim().toUpperCase();
}

function compareValues(left, right, direction = 'asc') {
  if (left == null && right == null) return 0;
  if (left == null) return 1;
  if (right == null) return -1;
  const result = typeof left === 'number' && typeof right === 'number' ? left - right : String(left).localeCompare(String(right));
  return direction === 'asc' ? result : -result;
}
const sortPositions = (positions) => [...positions].sort((a, b) => {
  if (positionSort.key === 'rating') {
    return compareValues(RATING_SORT_ORDER[a.rating] || 0, RATING_SORT_ORDER[b.rating] || 0, positionSort.direction);
  }
  return compareValues(a[positionSort.key], b[positionSort.key], positionSort.direction);
});
const RATING_SORT_ORDER = { 'Strong Sell': 1, Sell: 2, Hold: 3, 'Speculative Buy': 4, Buy: 5, 'Strong Buy': 6 };
const sortAnalysis = (items) => [...items].sort((a, b) => {
  if (analysisSort.key === 'rating') {
    return compareValues(RATING_SORT_ORDER[a.rating] || 0, RATING_SORT_ORDER[b.rating] || 0, analysisSort.direction);
  }
  return compareValues(a[analysisSort.key], b[analysisSort.key], analysisSort.direction);
});

function updateSortHeaderState() { positionSortHeaders.forEach((h) => { h.dataset.sortDirection = h.dataset.sortKey === positionSort.key ? positionSort.direction : ''; }); }
function updateAnalysisSortHeaderState() { analysisSortHeaders.forEach((h) => { h.dataset.sortDirection = h.dataset.sortKey === analysisSort.key ? analysisSort.direction : ''; }); }
function updateActionPlanSortHeaderState() { actionPlanLinearSortHeaders.forEach((h) => { h.dataset.sortDirection = h.dataset.sortKey === actionPlanLinearSort.key ? actionPlanLinearSort.direction : ''; }); }

function renderPositionsPortfolioSummary(summary = latestPositionsPortfolioSummary) {
  if (!positionsPortfolioSummaryEl) return;
  const data = summary || {};
  positionsPortfolioSummaryEl.innerHTML = `<div class="summary-item"><div class="label">Portfolio Value Used</div><div class="value">${formatCurrencyValue(data.portfolio_value_used ?? data.total_portfolio_value, 'USD')}</div></div><div class="summary-item"><div class="label">Actual Cash</div><div class="value">${formatCurrencyValue(data.actual_cash, 'USD')}</div></div><div class="summary-item"><div class="label">Cash-like Holdings</div><div class="value">${formatCurrencyValue(data.cash_equivalent_value, 'USD')}</div></div><div class="summary-item"><div class="label">Cash-like Available</div><div class="value">${formatCurrencyValue(data.cash_like_available, 'USD')}</div></div><div class="summary-item"><div class="label">Cash-like Available %</div><div class="value">${formatPercent(data.cash_like_available_percent)}</div></div>`;
  if (positionsPortfolioSummaryWarningEl) {
    if (data.portfolio_value_warning) {
      positionsPortfolioSummaryWarningEl.textContent = data.portfolio_value_warning;
      positionsPortfolioSummaryWarningEl.className = 'status warning';
    } else {
      positionsPortfolioSummaryWarningEl.textContent = '';
      positionsPortfolioSummaryWarningEl.className = 'status hidden';
    }
  }
}

function renderPositions() {
  positionsTableBody.innerHTML = '';
  sortPositions(getFilteredPositions()).forEach((position) => {
    const row = document.createElement('tr');
    const symbol = String(position.symbol ?? '');
    const rating = position.rating || '—';
    const upsideValue = typeof position.upside === 'number' ? formatPercent(position.upside) : '—';
    const upsideClass = typeof position.upside === 'number' ? valueClass(position.upside) : '';
    const expectedCagrValue = typeof position.expected_cagr === 'number' ? formatPercent(position.expected_cagr) : '—';
    const expectedCagrClass = typeof position.expected_cagr === 'number' ? valueClass(position.expected_cagr) : '';
    const confidenceValue = formatCoreConfidenceDisplay(position);
    const potentialConfidenceValue = formatPotentialConfidenceDisplay(position);
    row.innerHTML = `<td><button class="symbol-link" data-symbol="${escapeHtml(symbol)}">${escapeHtml(symbol)}</button></td><td>${rating}</td><td class="${upsideClass}">${upsideValue}</td><td class="${expectedCagrClass}">${expectedCagrValue}</td><td>${confidenceValue}</td><td>${potentialConfidenceValue}</td><td>${formatCurrencyValue(position.marketValue, position.currency)}</td><td>${formatCurrencyValue(position.costBasis, position.currency)}</td><td class="${valueClass(position.unrealizedPnL)}">${formatNumber(position.unrealizedPnL)}</td><td class="${valueClass(position.unrealizedPnLPercent)}">${formatPercent(position.unrealizedPnLPercent)}</td><td>${formatCurrencyValue(position.price, position.currency)}</td><td>${formatNumber(position.avgCost)}</td><td>${formatDate(position.latest_release_date)}</td><td class="${valueClass(position.dailyPnL)}">${formatNumber(position.dailyPnL)}</td><td class="${valueClass(position.changePercent)}">${formatPercent(position.changePercent)}</td>`;
    positionsTableBody.appendChild(row);
  });
  positionsTableBody.querySelectorAll('.symbol-link').forEach((btn) => btn.addEventListener('click', async () => openAnalysisDetailFromPositions(btn.dataset.symbol)));
}

function getFilteredPositions() {
  let items = latestPositions.filter((item) => Math.abs(Number(item?.position) || 0) > 0);
  const selectedRatings = getSelectedPositionRatings();
  if (selectedRatings.size > 0 && selectedRatings.size < RATING_FILTER_OPTIONS.length) {
    const expectedRatings = new Set(Array.from(selectedRatings).map((key) => RATING_FILTER_LABEL_BY_KEY[key]).filter(Boolean));
    items = items.filter((item) => expectedRatings.has(item.rating || ''));
  }
  return items;
}

function mergePositionsWithAnalysis(positions, analysisItems) {
  const normalizedAnalysisItems = Array.isArray(analysisItems)
    ? analysisItems
    : (analysisItems?.analysis || []);

  const analysisBySymbol = new Map(
    (normalizedAnalysisItems || [])
      .filter((item) => item && item.symbol)
      .map((item) => [normalizeSymbolForJoin(item.symbol), item]),
  );

  return (positions || []).map((position) => {
    const symbol = normalizeSymbolForJoin(position?.symbol);
    const matched = analysisBySymbol.get(symbol);
    if (!matched) return position;
    return {
      ...position,
      rating: position.rating ?? matched.rating,
      upside: typeof position.upside === 'number' ? position.upside : matched.upside,
      expected_cagr: typeof position.expected_cagr === 'number' ? position.expected_cagr : matched.expected_cagr,
      confidence_diff: typeof position.confidence_diff === 'number' ? position.confidence_diff : matched.confidence_diff,
      bullish_confidence: typeof position.bullish_confidence === 'number' ? position.bullish_confidence : matched.bullish_confidence,
      bearish_confidence: typeof position.bearish_confidence === 'number' ? position.bearish_confidence : matched.bearish_confidence,
      core_confidence_diff: typeof position.core_confidence_diff === 'number' ? position.core_confidence_diff : matched.core_confidence_diff,
      core_bullish_confidence: typeof position.core_bullish_confidence === 'number' ? position.core_bullish_confidence : matched.core_bullish_confidence,
      core_bearish_confidence: typeof position.core_bearish_confidence === 'number' ? position.core_bearish_confidence : matched.core_bearish_confidence,
      potential_confidence_diff: typeof position.potential_confidence_diff === 'number' ? position.potential_confidence_diff : matched.potential_confidence_diff,
      potential_bullish_confidence: typeof position.potential_bullish_confidence === 'number' ? position.potential_bullish_confidence : matched.potential_bullish_confidence,
      potential_bearish_confidence: typeof position.potential_bearish_confidence === 'number' ? position.potential_bearish_confidence : matched.potential_bearish_confidence,
      latest_release_date: position.latest_release_date || matched.latest_release_date || null,
    };
  });
}

function getPortfolioSymbols() {
  return new Set(
    latestPositions
      .filter((position) => Number(position?.position) > 0)
      .map((position) => String(position.symbol || '').toUpperCase())
      .filter(Boolean),
  );
}

function enrichAnalysisWithPortfolioStatus(items) {
  const portfolioSymbols = getPortfolioSymbols();
  return items.map((item) => ({
    ...item,
    inPortfolio: portfolioSymbols.has(String(item.symbol || '').toUpperCase()),
  }));
}

function getFilteredAnalysisItems() {
  let items = latestAnalysis;
  if (portfolioFilter === 'in_portfolio') items = items.filter((item) => item.inPortfolio === true);
  if (portfolioFilter === 'not_in_portfolio') items = items.filter((item) => item.inPortfolio === false);

  const selectedRatings = getSelectedRatings();
  if (selectedRatings.size > 0 && selectedRatings.size < RATING_FILTER_OPTIONS.length) {
    const expectedRatings = new Set(Array.from(selectedRatings).map((key) => RATING_FILTER_LABEL_BY_KEY[key]).filter(Boolean));
    items = items.filter((item) => expectedRatings.has(item.rating || 'Hold'));
  }

  return items;
}


function formatMomentumDisplay(score, label) {
  if (typeof score !== 'number') return '—';
  return `${score.toFixed(1)} / 5${label ? ` — ${label}` : ''}`;
}

function formatMomentumSummaryValue(score, label) {
  const hasScore = typeof score === 'number';
  const hasLabel = Boolean(label);
  if (hasScore && hasLabel) return `${score.toFixed(1)} / 5 — ${label}`;
  if (hasScore) return `${score.toFixed(1)} / 5`;
  if (hasLabel) return label;
  return '—';
}

function formatMomentumListLabel(score, label, status) {
  if (status === 'Error' || typeof score !== 'number' || !label) return '—';
  return label;
}

function getVisibleAnalysisSymbols() {
  return getFilteredAnalysisItems().map((item) => item.symbol).filter(Boolean);
}

function renderAnalysisList() {
  analysisTableBody.innerHTML = '';
  sortAnalysis(getFilteredAnalysisItems()).forEach((item) => {
    const row = document.createElement('tr');
    row.innerHTML = `<td><input type="checkbox" class="analysis-row-select" data-symbol="${item.symbol}" ${selectedAnalysisSymbols.has(item.symbol) ? 'checked' : ''}></td><td><button class="symbol-link" data-symbol="${item.symbol}">${item.symbol}</button></td><td>V${item.analysis_version || 'N/A'} / ${item.scenario_pass_count || 1}</td><td>${item.rating || 'Hold'}</td><td>${formatCurrencyValue(item.current_price, 'USD')}</td><td>${formatCurrencyValue(item.expected_price, 'USD')}</td><td class="${valueClass(item.expected_cagr)}">${formatPercent(item.expected_cagr)}</td><td class="${valueClass(item.upside)}">${formatPercent(item.upside)}</td><td>${formatMomentumListLabel(item.momentum_score, item.momentum_label, item.momentum_status)}</td><td>${formatMomentumListLabel(item.extension_risk, item.extension_label, item.momentum_status)}</td><td>${formatDateTime(item.momentum_updated_at)}</td><td><span class="badge ${item.inPortfolio ? 'badge-portfolio-in' : 'badge-portfolio-out'}">${item.inPortfolio ? 'In Portfolio' : 'Not in Portfolio'}</span></td><td>${formatCoreConfidenceDisplay(item)}</td><td>${formatPotentialConfidenceDisplay(item)}</td><td>${formatDate(item.latest_release_date)}</td><td>${formatDateTime(item.last_activity_at || item.updated_at)}</td><td><button class="remove-btn" data-symbol="${item.symbol}">Delete</button></td>`;
    analysisTableBody.appendChild(row);
  });
  analysisTableBody.querySelectorAll('.remove-btn').forEach((btn) => btn.addEventListener('click', async () => deleteAnalysis(btn.dataset.symbol)));
  analysisTableBody.querySelectorAll('.symbol-link').forEach((btn) => btn.addEventListener('click', async () => openAnalysisDetailForSymbol(btn.dataset.symbol, { origin: 'analysis' })));
  analysisTableBody.querySelectorAll('.analysis-row-select').forEach((checkbox) => {
    checkbox.addEventListener('change', () => {
      const symbol = checkbox.dataset.symbol;
      if (checkbox.checked) selectedAnalysisSymbols.add(symbol);
      else selectedAnalysisSymbols.delete(symbol);
      syncSelectAllCheckbox();
    });
  });
  syncSelectAllCheckbox();
}

function showActionPlanList() {
  selectedActionPlanDetail = null;
  actionPlanListViewEl.classList.remove('hidden');
  actionPlanDetailViewEl.classList.add('hidden');
}

function showActionPlanDetailView() {
  actionPlanListViewEl.classList.add('hidden');
  actionPlanDetailViewEl.classList.remove('hidden');
}

function getActionPlanAmountDetailLabel(item) {
  const label = item?.action_amount_label || '—';
  if (!item || item.action_amount_direction === 'none') return 'No action amount is needed for this recommendation.';
  if (item.action_amount_direction === 'sell') return `${label} based on current position market value.`;
  return `${label} to reach the calculated target midpoint.`;
}

function formatSuggestedShareCount(item) {
  const shares = Number(item?.suggested_share_count);
  return Number.isInteger(shares) && shares > 0 ? formatNumber(shares, 0) : '—';
}

function renderActionPlanMetricList(items) {
  return `<dl class="action-detail-metrics">${items.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${value}</dd></div>`).join('')}</dl>`;
}

function renderActionPlanMetricRows(rows) {
  const rowClass = (items) => (items.length === 1 ? 'single' : items.length === 2 ? 'two' : 'three');
  return `<div class="action-detail-metric-rows">${rows.map((items) => `<dl class="action-detail-metrics linear-score-card-row linear-score-card-row-${rowClass(items)}">${items.map(([label, value]) => `<div class="detail-metric-card"><dt>${escapeHtml(label)}</dt><dd>${value}</dd></div>`).join('')}</dl>`).join('')}</div>`;
}

function formatLinearPositionStatus(status) {
  const labels = {
    BELOW_TARGET: 'Below Target Band',
    INSIDE_TARGET: 'Inside Target Band',
    ABOVE_TARGET: 'Above Target Band',
    ZERO_TARGET_OWNED: 'Owned with Zero Target',
  };
  return escapeHtml(labels[status] || 'N/A');
}

function formatLinearGuardrailState(value) {
  return escapeHtml(value || 'N/A');
}

function formatLinearPenalties(items) {
  if (!Array.isArray(items) || !items.length) return 'None';
  return escapeHtml(items.map((item) => item.label || item.key).filter(Boolean).join(', ') || 'None');
}

function formatLinearPenaltyApplied(score) {
  const penalties = score?.penalties_applied;
  if (Array.isArray(penalties) && penalties.length) {
    const labels = penalties
      .map((item) => item?.label || (item?.key ? String(item.key).replace(/_/g, ' ') : ''))
      .filter(Boolean);
    return escapeHtml(labels.join('; ') || 'Penalty applied');
  }
  if (isFiniteNumber(score?.penalty_factor) && score.penalty_factor < 1) return 'Penalty applied';
  if (isFiniteNumber(score?.penalty_factor)) return 'None';
  return '—';
}

function formatLinearBonusApplied(score) {
  const reason = typeof score?.rating_bonus_reason === 'string' ? score.rating_bonus_reason.trim() : '';
  if (reason) return escapeHtml(reason);
  if (isFiniteNumber(score?.rating_bonus_factor) && score.rating_bonus_factor > 1) return 'Rating bonus applied';
  if (isFiniteNumber(score?.rating_bonus_factor)) return 'No rating bonus';
  return '—';
}

function formatFrontierOptionalityApplied(score) {
  const reason = typeof score?.frontier_optionality_applied_reason === 'string'
    ? score.frontier_optionality_applied_reason.trim()
    : '';
  if (score?.frontier_optionality_applied) return 'Yes';
  return reason ? `No — ${escapeHtml(reason)}` : 'No';
}

function getLinearTargetMarketValue(item) {
  const total = item?.portfolio_value_used ?? item?.total_portfolio_value;
  const targetMid = item?.target_weight_mid;
  if (!isFiniteNumber(total) || !isFiniteNumber(targetMid)) return null;
  return total * targetMid / 100;
}

function formatActionDetailCurrencyValue(value, currency, digits = 2) {
  return isFiniteNumber(value) ? formatCurrencyValue(value, currency, digits) : '—';
}

function formatActionDetailPercent(value) {
  return isFiniteNumber(value) ? formatPercent(value) : '—';
}

function formatActionDetailWeight(value) {
  return isFiniteNumber(value) ? formatPercent(value * 100) : '—';
}

function formatActionDetailNumber(value, digits = 2) {
  return isFiniteNumber(value) ? formatNumber(value, digits) : '—';
}

function formatActionDetailNet(value) {
  if (!isFiniteNumber(value)) return '—';
  return `${value >= 0 ? '+' : ''}${formatNumber(value)}`;
}

function renderActionPlanDetail(item) {
  if (!item) return;
  selectedActionPlanDetail = item;
  actionPlanDetailTitleEl.textContent = `Action Detail: ${item.symbol}`;
  actionPlanDetailStatusEl.textContent = item.linear_explanation || item.reason || '';
  actionPlanDetailStatusEl.className = item.final_scenario_stale ? 'status warning' : 'status';
  const target = item.linear_target_breakdown || {};
  const score = item.linear_score_breakdown || {};
  const weights = score.weights_used || {};
  const guardrails = item.guardrails || {};
  const targetBand = `${formatActionDetailPercent(item.target_weight_low)} – ${formatActionDetailPercent(item.target_weight_high)}`;
  actionPlanDetailContentEl.innerHTML = `
    <section class="detail-card"><h4>Action Summary</h4>${renderActionPlanMetricList([
      ['Symbol', escapeHtml(item.symbol || '')],
      ['Company Name', escapeHtml(item.company_name || '—')],
      ['Action', escapeHtml(item.action || 'Hold')],
      ['Action Amount', escapeHtml(item.action_amount_label || '—')],
      ['Action Shares Amount', formatSuggestedShareCount(item)],
      ['Rating', escapeHtml(item.rating || 'Hold')],
      ['Current Price', formatActionDetailCurrencyValue(item.current_price, 'USD')],
      ['Current Market Value', formatActionDetailCurrencyValue(item.current_position_market_value, 'USD')],
      ['Expected Price', formatActionDetailCurrencyValue(item.expected_price, 'USD')],
      ['Upside', formatActionDetailPercent(item.upside)],
      ['Expected CAGR', formatActionDetailPercent(item.expected_cagr)],
    ])}</section>
    <section class="detail-card"><h4>Position vs Target Band</h4>${renderActionPlanMetricList([
      ['Current Position Market Value', formatActionDetailCurrencyValue(item.current_position_market_value, 'USD')],
      ['Target Gap Amount', formatActionDetailCurrencyValue(item.target_gap_amount, 'USD')],
      ['Target Market Value', formatActionDetailCurrencyValue(getLinearTargetMarketValue(item), 'USD')],
      ['Current Position Weight', formatActionDetailPercent(item.current_position_weight)],
      ['Target Low', formatActionDetailPercent(item.target_weight_low)],
      ['Target Mid', formatActionDetailPercent(item.target_weight_mid)],
      ['Target High', formatActionDetailPercent(item.target_weight_high)],
      ['Gap to Mid', formatActionDetailPercent(item.position_gap_to_mid)],
    ])}</section>
    <section class="detail-card"><h4>Linear Target Calculation</h4>${renderActionPlanMetricRows([
      [['Linear Score', formatActionDetailNumber(score.linear_score ?? item.linear_allocation_score)]],
      [
        ['Core Confidence Weight', formatActionDetailWeight(weights.linear_core_confidence_weight)],
        ['Core Confidence Net', formatActionDetailNet(item.core_confidence_diff)],
        ['Core Confidence Score', formatActionDetailNumber(score.core_net_score)],
      ],
      [
        ['Upside Weight', formatActionDetailWeight(weights.linear_upside_weight)],
        ['Upside', formatActionDetailPercent(item.upside)],
        ['Upside Score', formatActionDetailNumber(score.upside_score)],
      ],
      [
        ['Expected CAGR Weight', formatActionDetailWeight(weights.linear_expected_cagr_weight)],
        ['Expected CAGR', formatActionDetailPercent(item.expected_cagr)],
        ['Expected CAGR Score', formatActionDetailNumber(score.expected_cagr_score)],
      ],
      [
        ['Potential Confidence Weight', formatActionDetailWeight(weights.linear_potential_confidence_weight)],
        ['Potential Confidence Net', formatActionDetailNet(item.potential_confidence_diff)],
        ['Potential Confidence Score', formatActionDetailNumber(score.potential_net_score)],
      ],
      [
        ['Confidence Quality Weight', formatActionDetailWeight(weights.linear_confidence_quality_weight)],
        ['Confidence Quality Score', formatActionDetailNumber(score.confidence_quality_score)],
      ],
      [
        ['Penalty Factor', formatActionDetailNumber(score.penalty_factor)],
        ['Penalty Applied', formatLinearPenaltyApplied(score)],
      ],
      [
        ['Rating Bonus Factor', formatActionDetailNumber(score.rating_bonus_factor)],
        ['Bonus Applied', formatLinearBonusApplied(score)],
      ],
      [
        ['Frontier Score', `${formatActionDetailNumber(score.frontier_optionality_score)} / 5`],
        ['Frontier Boost Factor', formatActionDetailNumber(score.frontier_optionality_boost_factor)],
        ['Frontier Boost Applied', formatFrontierOptionalityApplied(score)],
      ],
      [
        ['Linear Score Before Frontier Boost', formatActionDetailNumber(score.linear_score_before_frontier_boost)],
        ['Frontier Boost Reason', escapeHtml(score.frontier_optionality_applied_reason || '—')],
      ],
    ])}<div class="action-detail-explanation"><h5>How this target is calculated</h5><p>BakingMoney first converts Expected CAGR, Upside, Core Confidence Net, Potential Confidence Net, and Confidence Quality into component scores using the configured Linear ranges and weights. Penalty Factor and Rating Bonus Factor then adjust the score. If a company has a manually assigned Frontier Score, BakingMoney may apply a small capped boost before target allocation, unless a guardrail blocks it. The resulting Linear Score is then used to calculate target allocation, subject to stock-specific caps, Dynamic Reserve, and target band tolerances.</p></div></section>
    <section class="detail-card"><h4>Target Band Calculation</h4>${renderActionPlanMetricList([
      ['Current Position Weight', formatActionDetailPercent(item.current_position_weight)],
      ['Target Low', formatActionDetailPercent(item.target_weight_low)],
      ['Target Mid', formatActionDetailPercent(item.target_weight_mid)],
      ['Target High', formatActionDetailPercent(item.target_weight_high)],
      ['Target Band', targetBand],
      ['Linear Score', formatActionDetailNumber(score.linear_score ?? item.linear_allocation_score)],
      ['Score Allocation Power', formatActionDetailNumber(item.linear_score_allocation_power)],
      ['Powered Linear Score', formatActionDetailNumber(item.linear_powered_score ?? item.linear_allocation_weight)],
      ['Total Powered Linear Score', formatActionDetailNumber(item.linear_total_powered_score)],
      ['Target Allocation Pool', formatActionDetailPercent(item.linear_target_allocation_pool)],
      ['Pre-Cap Target Mid', formatActionDetailPercent(target.target_before_caps ?? item.linear_target_mid_before_caps ?? item.uncapped_target_mid)],
      ['Add Band Tolerance', formatActionDetailPercent(item.linear_add_band_tolerance_pct)],
      ['Trim Band Tolerance', formatActionDetailPercent(item.linear_trim_band_tolerance_pct)],
      ['Cap Applied', formatActionDetailPercent(target.cap_amount ?? item.cap_applied ?? item.linear_cap_applied)],
      ['Cap Reason', escapeHtml(target.cap_reason || item.cap_reason || item.linear_cap_reason || '—')],
      ['Pre-Reserve Target Mid', formatActionDetailPercent(target.target_after_cap_mid ?? item.pre_reserve_target_mid)],
      ['Reserve Scale Factor', formatActionDetailNumber(target.reserve_scale_factor ?? item.reserve_scale_factor)],
      ['Final Target Mid', formatActionDetailPercent(target.final_target_mid ?? item.target_weight_mid)],
    ])}<div class="action-detail-explanation"><h5>How this target band is calculated</h5><p>BakingMoney first converts the stock's Linear Score into a target midpoint. The Linear Score, after the minimum score threshold, is raised to the configured Score Allocation Power, then compared with the total powered scores of all eligible Linear stocks. That determines the stock's share of the Linear target allocation pool and produces the pre-cap Target Mid.</p><p>Stock-specific caps may reduce that midpoint. Dynamic Reserve may then scale all Linear targets down if total target allocation exceeds deployable equity. The final Target Mid is the post-cap, post-reserve midpoint. Target Low is calculated from Final Target Mid using the configured Add Band Tolerance, and Target High is calculated from Final Target Mid using the configured Trim Band Tolerance.</p></div></section>
    <section class="detail-card"><h4>Guardrails</h4>${renderActionPlanMetricList([
      ['Rating Guardrail', formatLinearGuardrailState(guardrails.rating)],
      ['Extension Risk Guardrail', formatLinearGuardrailState(guardrails.extension_risk)],
      ['Minimum Executable Trade', formatLinearGuardrailState(guardrails.minimum_executable_trade)],
      ['Whole-Share Minimum', formatLinearGuardrailState(guardrails.whole_share_minimum)],
    ])}</section>
    <section class="detail-card"><h4>Scenario Context</h4>${renderActionPlanMetricList([
      ['Current Price', formatCurrencyValue(item.current_price, 'USD')],
      ['Expected Price', formatCurrencyValue(item.expected_price, 'USD')],
      ['Upside', formatPercent(item.upside)],
      ['Expected CAGR', formatPercent(item.expected_cagr)],
      ['Rating', escapeHtml(item.rating || 'Hold')],
      ['Core Confidence', formatConfidenceDiffDisplay(item.core_confidence_diff, item.core_bullish_confidence, item.core_bearish_confidence)],
      ['Potential Confidence', formatConfidenceDiffDisplay(item.potential_confidence_diff, item.potential_bullish_confidence, item.potential_bearish_confidence)],
      ['Momentum', escapeHtml(formatLinearMomentum(item))],
      ['Extension Risk', isFiniteNumber(item.extension_risk) ? `${formatNumber(item.extension_risk)}${item.extension_label ? ` ${escapeHtml(item.extension_label)}` : ''}` : '—'],
      ['Release Date', escapeHtml(formatLinearReleaseDate(item))],
      ['Using Final Scenario Overlay', item.uses_final_scenario_overlay ? 'Yes' : 'No'],
      ['Final Scenario Stale', item.final_scenario_stale ? 'Yes' : 'No'],
    ])}</section>`;
  showActionPlanDetailView();
}

async function openActionPlanDetail(symbol) {
  const cached = (latestActionPlanPayload.linear_action_plan || []).find((item) => item.symbol === symbol);
  renderActionPlanDetail(cached || { symbol, action: 'Loading…' });
  actionPlanDetailStatusEl.textContent = `Loading ${symbol} Action Detail…`;
  try {
    const response = await fetch(`/api/action-plan/${encodeURIComponent(symbol)}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load Action Detail'));
    renderActionPlanDetail(payload.action_detail);
  } catch (error) {
    actionPlanDetailStatusEl.textContent = `Error: ${error.message}`;
    actionPlanDetailStatusEl.className = 'status error';
  }
}

async function loadActionPlan() {
  if (!actionPlanLinearActionsTableBody) return;
  showActionPlanList();
  actionPlanStatusEl.textContent = 'Loading Action Plan…';
  actionPlanStatusEl.className = 'status';
  try {
    const response = await fetch('/api/action-plan');
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load Action Plan'));
    latestActionPlanPayload = payload || { action_plan: [], summary: {} };
    renderActionPlan();
    actionPlanStatusEl.textContent = `Loaded ${payload.linear_action_plan?.length || 0} Linear Allocation rows.`;
    actionPlanStatusEl.className = 'status';
  } catch (error) {
    actionPlanStatusEl.textContent = `Error: ${error.message}`;
    actionPlanStatusEl.className = 'status error';
  }
}

function getFilteredActionPlanItems() {
  let items = latestActionPlanPayload.action_plan || [];

  const selectedRatings = getSelectedActionPlanRatings();
  if (selectedRatings.size > 0 && selectedRatings.size < RATING_FILTER_OPTIONS.length) {
    const expectedRatings = new Set(Array.from(selectedRatings).map((key) => RATING_FILTER_LABEL_BY_KEY[key]).filter(Boolean));
    items = items.filter((item) => expectedRatings.has(item.rating || 'Hold'));
  }

  const selectedActions = getSelectedActionPlanActions();
  if (selectedActions.size > 0 && selectedActions.size < ACTION_PLAN_ACTION_FILTER_OPTIONS.length) {
    items = items.filter((item) => selectedActions.has(getActionPlanActionFilterKey(item.action)));
  }

  return items;
}

function getFilteredLinearActionPlanItems() {
  let items = latestActionPlanPayload.linear_action_plan || [];
  const selectedRatings = getSelectedActionPlanRatings();
  if (selectedRatings.size > 0 && selectedRatings.size < RATING_FILTER_OPTIONS.length) {
    const expectedRatings = new Set(Array.from(selectedRatings).map((key) => RATING_FILTER_LABEL_BY_KEY[key]).filter(Boolean));
    items = items.filter((item) => expectedRatings.has(item.rating || 'Hold'));
  }
  const selectedActions = getSelectedActionPlanActions();
  if (selectedActions.size > 0 && selectedActions.size < ACTION_PLAN_ACTION_FILTER_OPTIONS.length) {
    items = items.filter((item) => selectedActions.has(getActionPlanActionFilterKey(item.action)));
  }
  return items;
}

function getActionPlanNumericSortValue(item, key) {
  if (!item || !key) return null;
  if (key === 'release_date') return getLinearReleaseDateSortValue(item);
  if (key === 'target_band') return window.ActionPlanSorting.getTargetBandMidpoint(item);
  if (key === 'expected_equity_cagr') return window.ActionPlanSorting.getLinearCagrValue(item);
  if (key === 'current_position_market_value') {
    const value = Number(item.current_position_market_value ?? item.market_value ?? item.position_market_value ?? 0);
    return Number.isFinite(value) ? value : 0;
  }
  if (key === 'core_confidence_diff') {
    const direct = Number(item.core_confidence_diff);
    if (Number.isFinite(direct)) return direct;
    const bullish = Number(item.core_bullish_confidence);
    const bearish = Number(item.core_bearish_confidence);
    return Number.isFinite(bullish) && Number.isFinite(bearish) ? bullish - bearish : null;
  }
  if (key === 'potential_confidence_diff') {
    const direct = Number(item.potential_confidence_diff);
    if (Number.isFinite(direct)) return direct;
    const bullish = Number(item.potential_bullish_confidence);
    const bearish = Number(item.potential_bearish_confidence);
    return Number.isFinite(bullish) && Number.isFinite(bearish) ? bullish - bearish : null;
  }
  const value = Number(item[key]);
  return Number.isFinite(value) ? value : null;
}

function sortActionPlanItemsWithState(items, sortState, secondarySort = null) {
  if (!sortState.key) return items;
  return window.ActionPlanSorting.sortRowsByNumericValue(items, {
    direction: sortState.direction,
    getValue: (item) => getActionPlanNumericSortValue(item, sortState.key),
    getSecondaryValue: secondarySort?.key
      ? (item) => getActionPlanNumericSortValue(item, secondarySort.key)
      : null,
    secondaryDirection: secondarySort?.direction,
  });
}

function sortActionPlanItems(items) {
  return sortActionPlanItemsWithState(items, actionPlanSort);
}

function sortLinearActionPlanItems(items) {
  return sortActionPlanItemsWithState(items, actionPlanLinearSort, { key: 'target_gap_amount', direction: 'desc' });
}

function sortLinearActionPlanDetailItems(items) {
  return sortActionPlanItemsWithState(items, actionPlanLinearDetailSort, { key: 'target_gap_amount', direction: 'desc' });
}

function setActionPlanActionMode(mode) {
  actionPlanActionMode = mode === 'linear' ? 'linear' : 'bucket';
  actionPlanModeBucketBtn?.classList.toggle('active', actionPlanActionMode === 'bucket');
  actionPlanModeLinearBtn?.classList.toggle('active', actionPlanActionMode === 'linear');
  actionPlanBucketActionsTableWrapEl?.classList.toggle('hidden', actionPlanActionMode !== 'bucket');
  actionPlanLinearActionsPanelEl?.classList.toggle('hidden', actionPlanActionMode !== 'linear');
  renderActionPlan();
}

function setActionPlanTab(tab) {
  actionPlanActiveTab = tab === 'buckets' ? 'buckets' : (tab === 'linear' ? 'linear' : 'actions');
  const showBuckets = actionPlanActiveTab === 'buckets';
  const showLinear = actionPlanActiveTab === 'linear';
  actionPlanTabActionsBtn?.classList.toggle('active', actionPlanActiveTab === 'actions');
  actionPlanTabBucketsBtn?.classList.toggle('active', showBuckets);
  actionPlanTabLinearBtn?.classList.toggle('active', showLinear);
  actionPlanActionsPanelEl?.classList.toggle('hidden', showBuckets || showLinear);
  actionPlanBucketsPanelEl?.classList.toggle('hidden', !showBuckets);
  actionPlanLinearDetailPanelEl?.classList.toggle('hidden', !showLinear);
  actionPlanLinearActionsPanelEl?.classList.toggle('hidden', actionPlanActiveTab !== 'actions' || actionPlanActionMode !== 'linear');
  if (showBuckets) renderActionPlanBuckets();
  renderActionPlan();
}

function getActionPlanBucketRows(bucket) {
  const rows = Array.isArray(latestActionPlanPayload?.action_plan) ? latestActionPlanPayload.action_plan : [];
  const bucketNames = bucket === 'Sell / Strong Sell' ? new Set(['Sell', 'Strong Sell']) : new Set([bucket]);
  const bucketRows = rows.filter((item) => bucketNames.has(item.bucket || item.rating || 'Hold')).sort((a, b) => {
    const targetDelta = (safeNumberForSort(b.target_weight_mid) ?? -Infinity) - (safeNumberForSort(a.target_weight_mid) ?? -Infinity);
    if (targetDelta) return targetDelta;
    const scoreDelta = (safeNumberForSort(b?.score_breakdown?.company_bucket_score) ?? -Infinity) - (safeNumberForSort(a?.score_breakdown?.company_bucket_score) ?? -Infinity);
    if (scoreDelta) return scoreDelta;
    return (safeNumberForSort(b.upside) ?? -Infinity) - (safeNumberForSort(a.upside) ?? -Infinity);
  });
  return sortActionPlanBucketRows(bucket, bucketRows);
}

function safeNumberForSort(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatLinearCagrPercent(item) {
  return window.ActionPlanSorting.formatCagrPercent(window.ActionPlanSorting.getLinearCagrValue(item));
}

function findActionPlanBucketSummary(bucket) {
  const summaries = latestActionPlanPayload?.summary?.bucket_summary || [];
  if (bucket === 'Sell / Strong Sell') {
    const sellBuckets = summaries.filter((item) => item.bucket === 'Sell' || item.bucket === 'Strong Sell');
    return sellBuckets.reduce((acc, item) => ({
      bucket,
      eligible_count: (acc.eligible_count || 0) + (item.eligible_count || 0),
      weighted_eligible_count: (acc.weighted_eligible_count || 0) + (item.weighted_eligible_count || 0),
      weighted_count_used: (acc.weighted_count_used || 0) + (item.weighted_count_used ?? item.effective_weighted_count_used ?? 0),
      max_effective_count: null,
      raw_target: (acc.raw_target || 0) + (item.raw_target ?? item.raw_bucket_target ?? item.bucket_target_percent ?? 0),
      effective_target: (acc.effective_target || 0) + (item.effective_target ?? item.bucket_target_percent ?? 0),
      compression_amount: (acc.compression_amount || 0) + (item.compression_amount || 0),
      allocated_before_caps: (acc.allocated_before_caps || 0) + (item.allocated_before_caps || 0),
      allocated_after_caps: (acc.allocated_after_caps || 0) + (item.allocated_after_caps ?? item.allocated_target_percent ?? 0),
      post_cap_unallocated: (acc.post_cap_unallocated || 0) + (item.post_cap_unallocated ?? item.unallocated_due_to_caps_percent ?? 0),
      status: sellBuckets.length ? 'Combined' : 'Empty',
    }), { bucket, status: 'Empty' });
  }
  return summaries.find((item) => item.bucket === bucket) || { bucket, status: 'Empty' };
}

function getBucketStatus(summary, rows) {
  if (!rows.length) return 'Empty';
  if ((summary.raw_target ?? summary.bucket_target_percent ?? 0) <= 0) return 'Zero target';
  if ((summary.compression_amount || 0) > 0) return 'Compressed';
  if ((summary.post_cap_unallocated ?? summary.unallocated_due_to_caps_percent ?? 0) > 0) return 'Underallocated';
  return summary.status || 'Normal';
}

function renderBucketMessages(bucket, summary, rows) {
  const messages = [];
  if ((summary.compression_amount || 0) > 0) messages.push('This bucket was compressed because raw equity demand exceeded available portfolio capacity.');
  if ((summary.post_cap_unallocated ?? summary.unallocated_due_to_caps_percent ?? 0) > 0) messages.push('This bucket is underallocated because one or more companies hit allocation caps.');
  if ((summary.weighted_eligible_count || 0) < 0.25 && (summary.eligible_count || 0) > 0) messages.push('This bucket has low weighted eligible count. Eligible companies have relatively weak allocation scores.');
  if (isFiniteNumber(summary.max_effective_count) && (summary.weighted_eligible_count || 0) > summary.max_effective_count + 1e-9) messages.push('This bucket is using its max effective count cap for sizing.');
  if (bucket === 'Speculative Buy') messages.push('Speculative Buy exposure is intentionally capped because these positions have higher uncertainty.');
  if (!rows.length) messages.push('No eligible companies in this bucket.');
  return messages.length ? `<div class="action-plan-bucket-messages">${messages.map((message) => `<p>${escapeHtml(message)}</p>`).join('')}</div>` : '';
}

function getCapReason(item) {
  const tb = item.target_weight_breakdown || {};
  const before = safeNumberForSort(tb.target_before_caps);
  const after = safeNumberForSort(tb.target_weight_mid ?? item.target_weight_mid);
  if (item.cap_reason && item.cap_reason !== '—') return item.cap_reason;
  if (tb.cap_reason && tb.cap_reason !== '—') return tb.cap_reason;
  if (before != null && after != null && before > after + 1e-9) return `Capped at ${formatPercent(tb.cap_applied)}`;
  return '—';
}

const ACTION_PLAN_BUCKET_COLUMNS = [
  { label: 'Symbol', sortable: false },
  { label: 'Action', sortable: false },
  { label: 'Current Weight', key: 'current_weight', sortable: true },
  { label: 'Target Mid', key: 'target_mid', sortable: true },
  { label: 'Target Band', key: 'target_band', sortable: true },
  { label: 'Gap to Mid', key: 'gap_to_mid', sortable: true },
  { label: 'Target Gap', key: 'target_gap_amount', sortable: true },
  { label: 'Action Amount', sortable: false },
  { label: 'Shares', key: 'suggested_share_count', sortable: true },
  { label: 'Funding Status', sortable: false },
  { label: 'Market Value', key: 'market_value', sortable: true },
  { label: 'Upside', key: 'upside', sortable: true },
  { label: 'Core Confidence', key: 'core_confidence_diff', sortable: true },
  { label: 'Potential Confidence', key: 'potential_confidence_diff', sortable: true },
  { label: 'Allocation Score', key: 'allocation_score', sortable: true },
  { label: 'Bucket Sizing Score', key: 'bucket_sizing_score', sortable: true },
  { label: 'Target Mid Before Caps', key: 'target_mid_before_caps', sortable: true },
  { label: 'Cap Reason', sortable: false },
];

function getActionPlanBucketSortValue(item, key) {
  const tb = item?.target_weight_breakdown || {};
  if (key === 'current_weight') return safeNumberForSort(item.current_position_weight);
  if (key === 'target_mid') return safeNumberForSort(item.target_weight_mid);
  if (key === 'target_band') return window.ActionPlanSorting.getTargetBandMidpoint(item);
  if (key === 'gap_to_mid') return safeNumberForSort(item.position_gap_to_mid);
  if (key === 'target_gap_amount') return safeNumberForSort(item.target_gap_amount);
  if (key === 'suggested_share_count') return safeNumberForSort(item.suggested_share_count);
  if (key === 'market_value') return safeNumberForSort(item.current_position_market_value ?? item.market_value ?? item.position_market_value);
  if (key === 'upside') return safeNumberForSort(item.upside);
  if (key === 'core_confidence_diff') return getActionPlanNumericSortValue(item, 'core_confidence_diff');
  if (key === 'potential_confidence_diff') return getActionPlanNumericSortValue(item, 'potential_confidence_diff');
  if (key === 'allocation_score') return safeNumberForSort(item.company_allocation_score ?? item.allocation_score ?? tb.company_allocation_score ?? tb.company_bucket_score ?? item?.score_breakdown?.company_allocation_score);
  if (key === 'bucket_sizing_score') return safeNumberForSort(item.bucket_sizing_score ?? tb.bucket_sizing_score ?? item?.score_breakdown?.bucket_sizing_score);
  if (key === 'target_mid_before_caps') return safeNumberForSort(item.target_mid_before_caps ?? tb.target_mid_before_caps ?? tb.target_before_caps);
  return null;
}

function sortActionPlanBucketRows(bucket, rows) {
  const sort = actionPlanBucketSorts[bucket];
  if (!sort?.key) return rows;
  return window.ActionPlanSorting.sortRowsByNumericValue(rows, {
    direction: sort.direction,
    getValue: (item) => getActionPlanBucketSortValue(item, sort.key),
  });
}

function renderActionPlanBucketHeaders(bucket) {
  const currentSort = actionPlanBucketSorts[bucket] || {};
  return ACTION_PLAN_BUCKET_COLUMNS.map((column) => {
    if (!column.sortable) return `<th>${escapeHtml(column.label)}</th>`;
    const direction = currentSort.key === column.key ? ` data-sort-direction="${escapeHtml(currentSort.direction)}"` : '';
    return `<th class="sortable action-plan-bucket-sortable" data-bucket="${escapeHtml(bucket)}" data-sort-key="${escapeHtml(column.key)}"${direction}>${escapeHtml(column.label)}</th>`;
  }).join('');
}

function renderActionPlanBucketCompanyTable(rows, bucket) {
  if (!rows.length) return '<p class="muted">No companies in this bucket.</p>';
  const body = rows.map((item) => {
    const tb = item.target_weight_breakdown || {};
    const targetBand = `${formatPercent(item.target_weight_low)} – ${formatPercent(item.target_weight_high)}`;
    const marketValue = isFiniteNumber(item.current_position_market_value) ? formatCurrencyValue(item.current_position_market_value, 'USD') : '—';
    return `<tr>
      <td><button class="symbol-link action-plan-bucket-symbol" data-symbol="${escapeHtml(item.symbol)}">${escapeHtml(item.symbol)}</button></td>
      <td>${escapeHtml(item.action || 'Hold')}</td>
      <td>${formatPercent(item.current_position_weight)}</td>
      <td>${formatPercent(item.target_weight_mid)}</td>
      <td>${targetBand}</td>
      <td class="${valueClass(item.position_gap_to_mid)}">${formatPercent(item.position_gap_to_mid)}</td>
      <td>${formatCurrencyValue(item.target_gap_amount, 'USD')}</td>
      <td>${escapeHtml(item.action_amount_label || '—')}</td>
      <td>${formatSuggestedShareCount(item)}</td>
      <td>${escapeHtml(item.funding_status || 'No funding needed')}</td>
      <td>${marketValue}</td>
      <td class="${valueClass(item.upside)}">${formatPercent(item.upside)}</td>
      <td>${formatConfidenceDiffDisplay(item.core_confidence_diff, item.core_bullish_confidence, item.core_bearish_confidence)}</td>
      <td>${formatConfidenceDiffDisplay(item.potential_confidence_diff, item.potential_bullish_confidence, item.potential_bearish_confidence)}</td>
      <td>${formatNumber(item.company_allocation_score ?? tb.company_allocation_score ?? tb.company_bucket_score ?? item?.score_breakdown?.company_allocation_score)}</td>
      <td>${formatNumber(item.bucket_sizing_score ?? tb.bucket_sizing_score ?? item?.score_breakdown?.bucket_sizing_score)}</td>
      <td>${formatPercent(item.target_mid_before_caps ?? tb.target_mid_before_caps ?? tb.target_before_caps)}</td>
      <td class="wrap-cell">${escapeHtml(getCapReason(item))}</td>
    </tr>`;
  }).join('');
  return `<div class="table-wrap action-plan-bucket-table-wrap"><table class="action-plan-bucket-table"><thead><tr>${renderActionPlanBucketHeaders(bucket)}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function renderBucketSizingDiagnostic(summary) {
  const totalWeighted = formatNumber(summary.weighted_eligible_count);
  const maxEffective = isFiniteNumber(summary.max_effective_count) ? formatNumber(summary.max_effective_count) : 'No cap';
  const weightPerStock = isFiniteNumber(summary.bucket_weight_per_effective_stock) ? ` · Bucket Weight / Effective Stock: ${formatPercent(summary.bucket_weight_per_effective_stock)}` : '';
  const uncappedTarget = isFiniteNumber(summary.uncapped_bucket_target) ? ` · Uncapped Bucket Target: ${formatPercent(summary.uncapped_bucket_target)}` : '';
  return `<p class="action-plan-bucket-diagnostic">Total Weighted Eligible Count: ${totalWeighted} · Max Effective Count: ${maxEffective}${weightPerStock}${uncappedTarget}</p>`;
}

function renderActionPlanBucketPanel(bucket) {
  const rows = getActionPlanBucketRows(bucket);
  const summary = findActionPlanBucketSummary(bucket);
  const status = getBucketStatus(summary, rows);
  const cards = [
    ['Eligible Companies', formatNumber(summary.eligible_count, 0)],
    ['Weighted Count Used', formatNumber(summary.weighted_count_used ?? summary.effective_weighted_count_used ?? summary.weighted_eligible_count)],
    ['Raw Bucket Target', formatPercent(summary.raw_target ?? summary.raw_bucket_target ?? summary.bucket_target_percent)],
    ['Effective Bucket Target', formatPercent(summary.effective_target ?? summary.bucket_target_percent)],
    ['Compression Applied', formatPercent(summary.compression_amount)],
    ['Allocated After Caps', formatPercent(summary.allocated_after_caps ?? summary.allocated_target_percent)],
    ['Post-Cap Unallocated', formatPercent(summary.post_cap_unallocated ?? summary.unallocated_due_to_caps_percent)],
    ['Bucket Status', escapeHtml(status)],
  ];
  return `<section class="detail-card action-plan-bucket-panel"><h4>${escapeHtml(bucket)}</h4><div class="summary-grid action-plan-bucket-summary">${cards.map(([label, value]) => `<div class="summary-item"><div class="label">${escapeHtml(label)}</div><div class="value">${value}</div></div>`).join('')}</div>${renderBucketSizingDiagnostic(summary)}${renderBucketMessages(bucket, summary, rows)}${renderActionPlanBucketCompanyTable(rows, bucket)}</section>`;
}

function renderActionPlanCashBucketPanel(summary) {
  const cards = [
    ['Cash / Unallocated Target', formatPercent(summary.cash_unallocated_target ?? summary.configured_cash_target_percent)],
    ['Actual Cash', formatCurrencyValue(summary.actual_cash, 'USD')],
    ['Cash-like Holdings', formatCurrencyValue(summary.cash_equivalent_value, 'USD')],
    ['Cash-like Available', formatCurrencyValue(summary.cash_like_available, 'USD')],
    ['Cash-like Available %', formatPercent(summary.cash_like_available_percent)],
    ['Post-Cap Unallocated', formatPercent(summary.post_cap_unallocated)],
    ['Underfilled Buckets', formatPercent(summary.unallocated_due_to_underfilled_buckets)],
    ['Final Allocated Stock Target', formatPercent(summary.final_allocated_stock_target ?? summary.allocated_target_total)],
    ['Effective Equity Target', formatPercent(summary.effective_equity_target ?? summary.raw_equity_target)],
    ['Raw Equity Demand', formatPercent(summary.raw_equity_target)],
    ['Compression Applied', formatPercent(summary.compression_applied)],
  ];
  return `<section class="detail-card action-plan-bucket-panel"><h4>Cash / Unallocated</h4><div class="summary-grid action-plan-bucket-summary">${cards.map(([label, value]) => `<div class="summary-item"><div class="label">${escapeHtml(label)}</div><div class="value">${value}</div></div>`).join('')}</div><p>Cash / Unallocated is the balancing allocation that keeps total effective bucket targets equal to 100%. It may include the minimum cash reserve, unused allocation from underfilled buckets, and allocation not assigned because of stock-level caps.</p></section>`;
}

function renderActionPlanBuckets() {
  if (!actionPlanBucketsContentEl) return;
  const summary = latestActionPlanPayload?.summary || {};
  const bucketSummary = summary.bucket_summary || [];
  if (!Array.isArray(bucketSummary) || !bucketSummary.length) {
    actionPlanBucketsContentEl.innerHTML = '<p class="status warning">Bucket summary is not available. Recalculate or refresh the Action Plan.</p>';
    return;
  }
  const total = summary.total_effective_bucket_target ?? summary.configured_bucket_total;
  const warning = Math.abs((Number(total) || 0) - 100) > 0.5 ? '<p class="status warning">Bucket targets do not sum to 100%. Please check Action Plan configuration.</p>' : '';
  const totals = [
    ['Raw Equity Demand', formatPercent(summary.raw_equity_target)],
    ['Effective Equity Target', formatPercent(summary.effective_equity_target)],
    ['Cash / Unallocated Target', formatPercent(summary.cash_unallocated_target ?? summary.configured_cash_target_percent)],
    ['Post-Cap Unallocated', formatPercent(summary.post_cap_unallocated)],
    ['Final Allocated Stock Target', formatPercent(summary.final_allocated_stock_target ?? summary.allocated_target_total)],
    ['Compression Applied', formatPercent(summary.compression_applied)],
    ['Total Effective Bucket Target', formatPercent(total)],
  ];
  const bucketPanels = ['Strong Buy', 'Buy', 'Speculative Buy', 'Hold', 'Sell / Strong Sell'].map(renderActionPlanBucketPanel).join('');
  actionPlanBucketsContentEl.innerHTML = `<section class="detail-card action-plan-bucket-total"><h4>Bucket Reconciliation</h4><div class="summary-grid action-plan-bucket-summary">${totals.map(([label, value]) => `<div class="summary-item"><div class="label">${escapeHtml(label)}</div><div class="value">${value}</div></div>`).join('')}</div>${warning}</section>${bucketPanels}${renderActionPlanCashBucketPanel(summary)}`;
  actionPlanBucketsContentEl.querySelectorAll('.action-plan-bucket-symbol').forEach((btn) => btn.addEventListener('click', async () => openActionPlanDetail(btn.dataset.symbol)));
  actionPlanBucketsContentEl.querySelectorAll('.action-plan-bucket-sortable').forEach((header) => header.addEventListener('click', () => {
    const bucket = header.dataset.bucket;
    const key = header.dataset.sortKey;
    if (!bucket || !key) return;
    const current = actionPlanBucketSorts[bucket] || {};
    actionPlanBucketSorts = {
      ...actionPlanBucketSorts,
      [bucket]: {
        key,
        direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc',
      },
    };
    renderActionPlanBuckets();
  }));
}

function getLinearCapAppliedAmount(item) {
  const amounts = [item?.cap_applied, item?.linear_cap_applied]
    .map((value) => Number(value))
    .filter(Number.isFinite);
  return amounts.length ? Math.max(...amounts) : null;
}

function hasLinearTargetCap(item) {
  const amount = getLinearCapAppliedAmount(item);
  return amount != null && amount > 0.0001;
}

function formatLinearTargetBand(low, mid, high) {
  return `${formatLinearCapPercent(low)} – ${formatLinearCapPercent(high)} (mid ${formatLinearCapPercent(mid)})`;
}

function formatLinearCapPercent(value) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? formatPercent(numericValue) : '—';
}

function formatLinearCapNumber(value) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? formatNumber(numericValue) : '—';
}

function closeLinearCapExplanationModal() {
  linearCapExplanationModalEl?.classList.add('hidden');
}

function openLinearCapExplanationModal(item) {
  if (!linearCapExplanationModalEl || !linearCapExplanationContentEl) return;
  const currentLow = item.adjusted_target_low ?? item.linear_target_weight_low ?? item.target_weight_low;
  const currentMid = item.adjusted_target_mid ?? item.linear_target_weight_mid ?? item.target_weight_mid;
  const currentHigh = item.adjusted_target_high ?? item.linear_target_weight_high ?? item.target_weight_high;
  const uncappedLow = item.uncapped_target_low;
  const uncappedMid = item.uncapped_target_mid ?? item.linear_target_mid_before_caps;
  const uncappedHigh = item.uncapped_target_high;
  const capAmount = getLinearCapAppliedAmount(item);
  const calculatedReduction = Number(uncappedMid) - Number(currentMid);
  const reduction = capAmount != null && capAmount > 0.0001
    ? capAmount
    : (Number.isFinite(calculatedReduction) && calculatedReduction > 0.0001 ? calculatedReduction : null);
  const reason = item.cap_reason || item.linear_cap_reason || '—';
  const details = [];
  if (Number.isFinite(Number(item.bearish_cap_progress)) && Number(item.bearish_cap_progress) > 0) {
    details.push(`Bearish confidence is ${formatLinearCapNumber(item.bearish_confidence ?? item.core_bearish_confidence)}; cap progress is ${formatLinearCapPercent(Number(item.bearish_cap_progress) * 100)}.`);
    details.push(`Configured bearish-confidence thresholds: ${formatLinearCapNumber(item.bearish_confidence_min_threshold)} to ${formatLinearCapNumber(item.bearish_confidence_max_threshold)}; full cap: ${formatLinearCapPercent(item.bearish_cap_full_limit)}.`);
  }
  if (item.bearish_cap_diagnostic) details.push(String(item.bearish_cap_diagnostic));
  const metricRows = [
    ['Symbol', escapeHtml(item.symbol || '—')],
    ['Reason', escapeHtml(reason)],
    ['Target before cap', formatLinearTargetBand(uncappedLow, uncappedMid, uncappedHigh)],
    ['Target after cap', formatLinearTargetBand(currentLow, currentMid, currentHigh)],
    ['Cap impact', reduction == null ? '—' : `${formatLinearCapPercent(reduction)} percentage points`],
    ['Effective cap', formatLinearCapPercent(item.linear_effective_cap)],
  ];
  linearCapExplanationContentEl.innerHTML = `${renderActionPlanMetricList(metricRows)}${details.length ? `<section class="cap-explanation-details"><h4>Details</h4>${details.map((detail) => `<p>${escapeHtml(detail)}</p>`).join('')}</section>` : ''}`;
  linearCapExplanationModalEl.classList.remove('hidden');
  linearCapExplanationCloseBtn?.focus();
}

function renderLinearAllocationRows() {
  const rows = Array.isArray(latestActionPlanPayload?.linear_action_plan) ? latestActionPlanPayload.linear_action_plan : [];
  const actionRows = sortLinearActionPlanItems(getFilteredLinearActionPlanItems());
  if (actionPlanLinearActionsTableBody) {
    actionPlanLinearActionsTableBody.innerHTML = '';
    actionRows.forEach((item) => {
      const row = document.createElement('tr');
      const cagr = window.ActionPlanSorting.getLinearCagrValue(item);
      const targetBand = `<span class="target-band-range">${formatPercent(item.linear_target_weight_low ?? item.target_weight_low)} – ${formatPercent(item.linear_target_weight_high ?? item.target_weight_high)}</span><span class="target-band-mid">(mid ${formatPercent(item.linear_target_weight_mid ?? item.target_weight_mid)})</span>`;
      const releaseTitle = item.release_date ? `Next known earnings release date: ${formatLinearReleaseDate(item).replace(/ BMO| AMC/, '')}${item.release_timing ? `, ${item.release_timing}` : ''}.` : 'Next known earnings release date from BakingMoney earnings calendar.';
      const momentumTitle = Number.isFinite(Number(item.momentum_score)) ? `Momentum: ${Number(item.momentum_score).toFixed(1)}/5${item.momentum_label ? ` ${item.momentum_label}` : ''}${item.momentum_updated_at ? `. Updated: ${item.momentum_updated_at}` : ''}.` : 'Momentum score and label from the stored deterministic momentum snapshot.';
      row.innerHTML = `<td class="symbol-cell"><button class="symbol-link linear-allocation-symbol" data-symbol="${escapeHtml(item.symbol)}">${escapeHtml(item.symbol)}</button></td><td class="action-cell">${escapeHtml(item.action || 'Hold')}</td><td class="market-value-cell">${formatCurrencyValue(item.current_position_market_value ?? 0, 'USD')}</td><td class="target-gap-cell">${formatCurrencyValue(item.target_gap_amount, 'USD')}</td><td class="action-amount-cell">${escapeHtml(item.action_amount_label || '—')}</td><td class="shares-cell">${formatSuggestedShareCount(item)}</td><td class="funding-cell">${escapeHtml(item.funding_status || 'No funding needed')}</td><td class="current-price-cell">${formatCurrencyValue(item.current_price, 'USD')}</td><td class="rating-cell">${escapeHtml(item.rating || 'Hold')}</td><td class="release-date-cell" title="${escapeHtml(releaseTitle)}">${escapeHtml(formatLinearReleaseDate(item))}${renderLinearReleaseDateWarning(item)}</td><td class="upside-cell ${valueClass(item.upside)}">${formatPercent(item.upside)}</td><td class="cagr-cell ${valueClass(cagr)}">${formatLinearCagrPercent(item)}</td><td class="core-confidence-cell">${formatConfidenceDiffDisplay(item.core_confidence_diff, item.core_bullish_confidence, item.core_bearish_confidence)}</td><td class="potential-confidence-cell">${formatConfidenceDiffDisplay(item.potential_confidence_diff, item.potential_bullish_confidence, item.potential_bearish_confidence)}</td><td class="momentum-cell" title="${escapeHtml(momentumTitle)}">${escapeHtml(formatLinearMomentum(item))}</td><td class="current-weight-cell">${formatPercent(item.current_position_weight)}</td><td class="target-band-cell">${targetBand}</td><td class="gap-cell ${valueClass(item.position_gap_to_mid)}">${formatPercent(item.position_gap_to_mid)}</td><td class="linear-score-cell">${formatNumber(item.linear_allocation_score)}</td>`;
      actionPlanLinearActionsTableBody.appendChild(row);
      if (hasLinearTargetCap(item)) {
        const warningButton = document.createElement('button');
        warningButton.type = 'button';
        warningButton.className = 'cap-warning-button';
        warningButton.dataset.symbol = item.symbol || '';
        warningButton.setAttribute('aria-label', `View target cap explanation for ${item.symbol || 'this stock'}`);
        warningButton.title = 'View target cap explanation';
        warningButton.textContent = '⚠';
        const targetBandRange = row.querySelector('.target-band-range');
        if (targetBandRange) targetBandRange.after(warningButton);
      }
    });
    actionPlanLinearActionsTableBody.querySelectorAll('.linear-allocation-symbol').forEach((btn) => btn.addEventListener('click', async () => openActionPlanDetail(btn.dataset.symbol)));
    actionPlanLinearActionsTableBody.querySelectorAll('.cap-warning-button').forEach((btn) => btn.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      const item = actionRows.find((candidate) => candidate.symbol === btn.dataset.symbol);
      if (item) openLinearCapExplanationModal(item);
    }));
  }

  if (actionPlanLinearDetailTableBody) {
    actionPlanLinearDetailTableBody.innerHTML = '';
    sortLinearActionPlanDetailItems(rows).forEach((item) => {
      const row = document.createElement('tr');
      const cagr = window.ActionPlanSorting.getLinearCagrValue(item);
      const targetBand = `<span class="target-band-range">${formatPercent(item.linear_target_weight_low ?? item.target_weight_low)} – ${formatPercent(item.linear_target_weight_high ?? item.target_weight_high)}</span><span class="target-band-mid">(mid ${formatPercent(item.linear_target_weight_mid ?? item.target_weight_mid)})</span>`;
      row.innerHTML = `<td><button class="symbol-link linear-allocation-symbol" data-symbol="${escapeHtml(item.symbol)}">${escapeHtml(item.symbol)}</button></td>
        <td>${escapeHtml(item.company_name || '—')}</td>
        <td>${escapeHtml(item.rating || 'Hold')}</td>
        <td>${formatCurrencyValue(item.current_position_market_value, 'USD')}</td>
        <td>${formatPercent(item.current_position_weight)}</td>
        <td>${formatPercent(item.linear_target_weight_mid ?? item.target_weight_mid)}</td>
        <td>${targetBand}</td>
        <td class="${valueClass(item.position_gap_to_mid)}">${formatPercent(item.position_gap_to_mid)}</td>
        <td>${formatCurrencyValue(item.target_gap_amount, 'USD')}</td>
        <td class="${valueClass(item.upside)}">${formatPercent(item.upside)}</td>
        <td class="${valueClass(cagr)}">${formatLinearCagrPercent(item)}</td>
        <td>${formatNumber(item.linear_allocation_score)}</td>
        <td class="${valueClass(item.core_confidence_diff)}">${formatNumber(item.core_confidence_diff)}</td>
        <td class="${valueClass(item.potential_confidence_diff)}">${formatNumber(item.potential_confidence_diff)}</td>
        <td>${formatNumber(item.core_bullish_confidence)}</td>
        <td>${formatNumber(item.core_bearish_confidence)}</td>
        <td>${formatPercent(item.cap_applied ?? item.linear_cap_applied)}</td>
        <td>${escapeHtml(item.cap_reason || item.linear_cap_reason || '—')}</td>
        <td>${escapeHtml(item.funding_status || 'No funding needed')}</td>
        <td>${escapeHtml(item.action_amount_label || '—')}</td>
        <td>${formatSuggestedShareCount(item)}</td>`;
      actionPlanLinearDetailTableBody.appendChild(row);
    });
    actionPlanLinearDetailTableBody.querySelectorAll('.linear-allocation-symbol').forEach((btn) => btn.addEventListener('click', async () => openActionPlanDetail(btn.dataset.symbol)));
  }
}

function renderActionPlanSummaryCards(summary, modeLabel) {
  if (modeLabel === 'Linear Allocation') {
    const reserveBalanceLabel = (summary.reserve_shortfall || 0) > 0 ? 'Reserve Shortfall' : 'Reserve Excess Before Buys';
    const reserveBalanceValue = (summary.reserve_shortfall || 0) > 0 ? summary.reserve_shortfall : summary.reserve_excess;
    return `<div class="summary-item summary-mode-card"><div class="label">Active Mode</div><div class="value">Linear Allocation</div></div>
      <div class="summary-item"><div class="label">Opportunity Score</div><div class="value">${formatPercent(isFiniteNumber(summary.portfolio_opportunity_score) ? summary.portfolio_opportunity_score * 100 : null)}</div></div>
      <div class="summary-item"><div class="label">Dynamic Reserve Target</div><div class="value">${formatPercent(summary.dynamic_reserve_pct)}</div></div>
      <div class="summary-item"><div class="label">Max Equity Allocation</div><div class="value">${formatPercent(summary.maximum_deployable_equity_pct)}</div></div>
      <div class="summary-item"><div class="label">Reserve Benchmark</div><div class="value">${formatPercent(summary.reserve_benchmark_yield)}</div></div>
      <div class="summary-item"><div class="label">Reserve Target Amount</div><div class="value">${formatCurrencyValue(summary.target_reserve_amount, 'USD')}</div></div>
      <div class="summary-item"><div class="label">Current Cash / Unallocated</div><div class="value">${formatCurrencyValue(summary.current_cash_unallocated, 'USD')}</div></div>
      <div class="summary-item"><div class="label">${reserveBalanceLabel}</div><div class="value">${formatCurrencyValue(reserveBalanceValue, 'USD')}</div></div>
      <div class="summary-item"><div class="label">Reserve Scale Factor</div><div class="value">${formatNumber(summary.reserve_scale_factor)}</div></div>
      <div class="summary-item"><div class="label">Linear Allocated Target Total</div><div class="value">${formatPercent(summary.linear_allocated_target_total ?? summary.linear_configured_target_total)}</div></div>
      <div class="summary-item"><div class="label">Current Equity Allocation</div><div class="value">${formatPercent(summary.current_equity_allocation)}</div></div>
      <div class="summary-item"><div class="label">Available Buy Budget</div><div class="value">${formatCurrencyValue(summary.cash_available_for_linear_buys ?? summary.available_buy_budget, 'USD')}</div></div>
      <div class="summary-item"><div class="label">Total Linear Add Demand</div><div class="value">${formatCurrencyValue(summary.total_add_demand, 'USD')}</div></div>
      <div class="summary-item"><div class="label">Funded Linear Add Amount</div><div class="value">${formatCurrencyValue(summary.funded_add_amount, 'USD')}</div></div>
      <div class="summary-item"><div class="label">Unfunded Linear Add Demand</div><div class="value">${formatCurrencyValue(summary.unfunded_add_demand, 'USD')}</div></div>
      <div class="summary-item"><div class="label">Eligible Stocks</div><div class="value">${formatNumber(summary.eligible_stock_count, 0)}</div></div>
      <div class="summary-item"><div class="label">Capped Stocks</div><div class="value">${formatNumber(summary.capped_stock_count, 0)}</div></div>
      ${summary.reserve_configuration_valid === false ? '<p class="status warning">Dynamic Reserve configuration is invalid; the minimum reserve is being protected.</p>' : ''}
      ${summary.execution_warning ? `<p class="status warning">${escapeHtml(summary.execution_warning)}</p>` : ''}`;
  }
  return `<div class="summary-item summary-mode-card"><div class="label">Active Mode</div><div class="value">Bucket Allocation</div></div><div class="summary-item"><div class="label">Portfolio Value Used</div><div class="value">${formatCurrencyValue(summary.portfolio_value_used ?? summary.total_portfolio_value, 'USD')}</div></div><div class="summary-item"><div class="label">Actual Cash</div><div class="value">${formatCurrencyValue(summary.actual_cash, 'USD')}</div></div><div class="summary-item"><div class="label">Cash-like Holdings</div><div class="value">${formatCurrencyValue(summary.cash_equivalent_value, 'USD')}</div></div><div class="summary-item"><div class="label">Cash-like Available</div><div class="value">${formatCurrencyValue(summary.cash_like_available, 'USD')}</div></div><div class="summary-item"><div class="label">Available Buy Budget</div><div class="value">${formatCurrencyValue(summary.available_buy_budget, 'USD')}</div></div><div class="summary-item"><div class="label">Total Add Demand</div><div class="value">${formatCurrencyValue(summary.total_add_demand, 'USD')}</div></div><div class="summary-item"><div class="label">Funded Add Amount</div><div class="value">${formatCurrencyValue(summary.funded_add_amount, 'USD')}</div></div><div class="summary-item"><div class="label">Unfunded Add Demand</div><div class="value">${formatCurrencyValue(summary.unfunded_add_demand, 'USD')}</div></div><div class="summary-item"><div class="label">Executable Sell/Trim Proceeds</div><div class="value">${formatCurrencyValue(summary.executable_sell_trim_proceeds, 'USD')}</div></div><div class="summary-item"><div class="label">Minimum Cash Reserve</div><div class="value">${formatCurrencyValue(summary.minimum_cash_reserve_amount, 'USD')}</div></div><div class="summary-item"><div class="label">Allocated Target Total</div><div class="value">${formatPercent(summary.allocated_target_total)}</div></div><div class="summary-item"><div class="label">Unallocated Target Capacity</div><div class="value">${formatPercent(summary.unallocated_target_capacity ?? summary.unallocated_target_total)}</div></div>`;
}

function renderActionPlan() {
  const summary = latestActionPlanPayload?.summary?.linear_summary || {};
  actionPlanSummaryEl.innerHTML = renderActionPlanSummaryCards(summary, 'Linear Allocation');
  renderLinearAllocationRows();
  return;
  if (actionPlanBucketActionsTableWrapEl) actionPlanBucketActionsTableWrapEl.classList.toggle('hidden', actionPlanActiveTab !== 'actions' || actionPlanActionMode !== 'bucket');
  if (actionPlanLinearActionsPanelEl) actionPlanLinearActionsPanelEl.classList.toggle('hidden', !(actionPlanActiveTab === 'actions' && actionPlanActionMode === 'linear'));
  if (actionPlanLinearDetailPanelEl) actionPlanLinearDetailPanelEl.classList.toggle('hidden', actionPlanActiveTab !== 'linear');
  actionPlanTableBody.innerHTML = '';
  sortActionPlanItems(getFilteredActionPlanItems()).forEach((item) => {
    const row = document.createElement('tr');
    const targetBand = `<span class="target-band-range">${formatPercent(item.target_weight_low)} – ${formatPercent(item.target_weight_high)}</span><span class="target-band-mid">(mid ${formatPercent(item.target_weight_mid)})</span>`;
    row.innerHTML = `<td class="symbol-cell"><button class="symbol-link" data-symbol="${escapeHtml(item.symbol)}">${escapeHtml(item.symbol)}</button></td><td class="action-cell">${escapeHtml(item.action)}</td><td class="target-gap-cell">${formatCurrencyValue(item.target_gap_amount, 'USD')}</td><td class="action-amount-cell">${escapeHtml(item.action_amount_label || '—')}</td><td class="shares-cell">${formatSuggestedShareCount(item)}</td><td class="funding-cell">${escapeHtml(item.funding_status || 'No funding needed')}</td><td class="trigger-price-cell">${formatCurrencyValue(item.trigger_price, 'USD')}</td><td class="current-price-cell">${formatCurrencyValue(item.current_price, 'USD')}</td><td class="distance-cell ${valueClass(item.distance_to_trigger_percent)}">${formatPercent(item.distance_to_trigger_percent)}</td><td class="rating-cell">${escapeHtml(item.rating || 'Hold')}</td><td class="upside-cell ${valueClass(item.upside)}">${formatPercent(item.upside)}</td><td class="core-confidence-cell">${formatConfidenceDiffDisplay(item.core_confidence_diff, item.core_bullish_confidence, item.core_bearish_confidence)}</td><td class="potential-confidence-cell">${formatConfidenceDiffDisplay(item.potential_confidence_diff, item.potential_bullish_confidence, item.potential_bearish_confidence)}</td><td class="current-weight-cell">${formatPercent(item.current_position_weight)}</td><td class="target-band-cell">${targetBand}</td><td class="gap-cell ${valueClass(item.position_gap_to_mid)}">${formatPercent(item.position_gap_to_mid)}</td><td class="reason-cell">${escapeHtml(item.reason)}</td>`;
    actionPlanTableBody.appendChild(row);
  });
  actionPlanTableBody.querySelectorAll('.symbol-link').forEach((btn) => btn.addEventListener('click', async () => openActionPlanDetail(btn.dataset.symbol)));
  if (actionPlanActiveTab === 'buckets') renderActionPlanBuckets();
}

function syncSelectAllCheckbox() {
  const selectable = getFilteredAnalysisItems().map((item) => item.symbol);
  if (!selectable.length) {
    analysisSelectAllEl.checked = false;
    return;
  }
  analysisSelectAllEl.checked = selectable.every((symbol) => selectedAnalysisSymbols.has(symbol));
}

function showAnalysisList() { analysisListView.classList.remove('hidden'); analysisDetailView.classList.add('hidden'); }
function updateAnalysisBackButton() {
  if (analysisDetailOrigin === 'positions') {
    analysisBackBtn.textContent = '← Back to My Positions';
  } else if (analysisDetailOrigin === 'action_plan') {
    analysisBackBtn.textContent = '← Back to Action Plan';
  } else if (analysisDetailOrigin === 'earnings_review') {
    analysisBackBtn.textContent = '← Back to Earnings Review';
  } else {
    analysisBackBtn.textContent = '← Back to Analysis';
  }
}
function showAnalysisDetailFromOriginMenu(originView) {
  views.forEach((view) => view.classList.toggle('active', view.id === 'analysis'));
  menuItems.forEach((item) => item.classList.toggle('active', item.dataset.view === originView));
}
function showAnalysisDetailFromPositionsOrigin() {
  showAnalysisDetailFromOriginMenu('positions');
}
function showAnalysisDetailFromActionPlanOrigin() {
  showAnalysisDetailFromOriginMenu('action-plan');
}
function showAnalysisDetailFromEarningsReviewOrigin() {
  showAnalysisDetailFromOriginMenu('earnings-review');
}
function loadBackupView() {
  if (!backupStatusEl) return;
  backupStatusEl.textContent = 'Export a portable backup package (.zip) or restore one from another computer.';
  backupStatusEl.className = 'status';
}

async function restoreBackupFile() {
  if (!backupImportFileEl?.files?.length) {
    backupStatusEl.textContent = 'Please choose a .zip backup package first.';
    backupStatusEl.className = 'status error';
    return;
  }

  const file = backupImportFileEl.files[0];
  if (!file.name.toLowerCase().endsWith('.zip')) {
    backupStatusEl.textContent = 'Only .zip backup packages are supported.';
    backupStatusEl.className = 'status error';
    return;
  }

  const confirmed = window.confirm('Restore this backup and replace your current local database? This cannot be undone.');
  if (!confirmed) return;

  backupStatusEl.textContent = 'Restoring backup…';
  backupStatusEl.className = 'status';
  backupImportBtn.disabled = true;
  try {
    const restoreEnv = backupRestoreEnvEl?.checked ? '1' : '0';
    const response = await fetch(`/api/backup/import?restore_env=${restoreEnv}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/zip', 'X-Backup-Filename': file.name },
      body: file,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Restore failed.'));
    backupStatusEl.textContent = 'Backup restored successfully. Reloading app…';
    backupStatusEl.className = 'status';
    setTimeout(() => window.location.reload(), 900);
  } catch (error) {
    backupStatusEl.textContent = `Error: ${error.message}`;
    backupStatusEl.className = 'status error';
  } finally {
    backupImportBtn.disabled = false;
  }
}

function parseDownloadFilename(contentDispositionValue, fallbackName) {
  if (!contentDispositionValue) return fallbackName;
  const utf8Match = contentDispositionValue.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch (_error) {
      return utf8Match[1];
    }
  }
  const basicMatch = contentDispositionValue.match(/filename=\"?([^\";]+)\"?/i);
  return basicMatch?.[1] || fallbackName;
}

async function exportBackupFile() {
  backupStatusEl.textContent = 'Preparing backup download…';
  backupStatusEl.className = 'status';
  backupExportBtn.disabled = true;
  try {
    const includeEnv = backupIncludeEnvEl?.checked ? '1' : '0';
    const response = await fetch(`/api/backup/export?include_env=${includeEnv}`);
    if (!response.ok) {
      let payload = null;
      try { payload = await response.json(); } catch (_error) { payload = null; }
      throw new Error(extractErrorMessage(payload, 'Unable to download backup.'));
    }
    const blob = await response.blob();
    const filename = parseDownloadFilename(response.headers.get('Content-Disposition'), `bakingmoney-backup-${new Date().toISOString().slice(0, 16).replace('T', '-')}.zip`);
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(objectUrl);
    backupStatusEl.textContent = 'Backup file generation completed';
    backupStatusEl.className = 'status';
  } catch (error) {
    backupStatusEl.textContent = `Error: ${error.message}`;
    backupStatusEl.className = 'status error';
  } finally {
    backupExportBtn.disabled = false;
  }
}

function setView(targetView, options = {}) {
  const skipLoad = options.skipLoad === true;
  menuItems.forEach((item) => item.classList.toggle('active', item.dataset.view === targetView));
  views.forEach((view) => view.classList.toggle('active', view.id === targetView));
  if (targetView === 'analysis') { showAnalysisList(); if (!skipLoad) loadAnalysis(); }
  if (targetView === 'positions' && !skipLoad) loadPositions();
  if (targetView === 'action-plan' && !skipLoad) loadActionPlan();
  if (targetView === 'alerts') loadAlerts();
  if (targetView === 'prompt') loadPromptConfiguration();
  if (targetView === 'configuration') loadGeneralConfiguration();
  if (targetView === 'backup') loadBackupView();
}
menuItems.forEach((item) => item.addEventListener('click', () => {
  const target = item.dataset.view;
  setView(target);
  if (target === 'earnings-review') {
    setEarningsReviewTab('calendar');
    loadEarningsReview();
  }
}));

function showEarningsReviewList() {
  earningsReviewListView.classList.remove('hidden');
  earningsReviewSymbolView.classList.add('hidden');
  earningsReviewDetailView.classList.add('hidden');
}

function showEarningsReviewDetail() {
  earningsReviewListView.classList.add('hidden');
  earningsReviewSymbolView.classList.add('hidden');
  earningsReviewDetailView.classList.remove('hidden');
}

function getEffectiveBusinessModel() {
  const businessModelEdit = analysisDetailState?.saved_business_model_edit;
  if (businessModelEdit && Number(businessModelEdit.based_on_version_id) === Number(analysisDetailState.version.id)) {
    return businessModelEdit.business_model || '';
  }
  return analysisDetailState?.version?.business_model || '';
}

function getEffectiveBusinessSummary() {
  const businessSummaryEdit = analysisDetailState?.saved_business_summary_edit;
  if (businessSummaryEdit && Number(businessSummaryEdit.based_on_version_id) === Number(analysisDetailState.version.id)) {
    return businessSummaryEdit.business_summary || '';
  }
  return analysisDetailState?.version?.business_summary || '';
}

function selectedVersionIndex() {
  if (!analysisDetailState) return -1;
  return (analysisDetailState.versions || []).findIndex((v) => Number(v.id) === Number(analysisDetailState.selected_version_id));
}

function getSelectedAnalysisReleaseEntry() {
  const history = analysisDetailState?.release_history || [];
  if (!history.length) return null;
  const rawIndex = Number.isInteger(analysisDetailState.selected_release_index) ? analysisDetailState.selected_release_index : 0;
  const index = Math.max(0, Math.min(rawIndex, history.length - 1));
  analysisDetailState.selected_release_index = index;
  return history[index] || null;
}

function formatAnalysisReleaseEntry(entry) {
  if (!entry) return 'N/A';
  const parts = [];
  const dateText = entry.release_date ? formatDate(entry.release_date) : '';
  const period = [entry.fiscal_quarter, entry.fiscal_year].filter(Boolean).join(' ');
  if (dateText && dateText !== 'N/A') parts.push(dateText);
  if (period) parts.push(period);
  return parts.length ? parts.join(' • ') : 'N/A';
}

function renderAnalysisReleaseSummaryCard() {
  const history = analysisDetailState?.release_history || [];
  const selected = getSelectedAnalysisReleaseEntry();
  const selectedIndex = Number.isInteger(analysisDetailState?.selected_release_index) ? analysisDetailState.selected_release_index : 0;
  const showUp = history.length > 1 && selectedIndex > 0;
  const showDown = history.length > 1 && selectedIndex < history.length - 1;
  const buttons = history.length > 1
    ? `<div class="release-history-controls">${showUp ? '<button type="button" class="release-history-btn" data-release-nav="up">Up</button>' : ''}${showDown ? '<button type="button" class="release-history-btn" data-release-nav="down">Down</button>' : ''}</div>`
    : '';
  return `<div class="summary-item earnings-release-summary-item"><div class="label">Earnings Release</div><div class="value">${escapeHtml(formatAnalysisReleaseEntry(selected))}</div>${buttons}</div>`;
}

function getExternalScenarioTemplate() {
  return JSON.stringify({
    scenarios: [
      { name: 'Bear', price_low: 80, price_high: 100, probability: 25 },
      { name: 'Base', price_low: 120, price_high: 150, probability: 50 },
      { name: 'Bull', price_low: 180, price_high: 220, probability: 25 },
    ],
  }, null, 2);
}

function externalScenarioWeightPercent(item) {
  const value = Number(item?.external_weight_percent ?? (Number(item?.external_weight) * 100));
  return Number.isFinite(value) ? value : 0;
}

function getCurrentExternalScenarios() {
  return analysisDetailState?.external_scenarios || [];
}

function hasExternalScenarioOverlay() {
  return getCurrentExternalScenarios().length > 0;
}

function renderScenarioRows(scenarios, targetBody = analysisScenariosBody) {
  targetBody.innerHTML = '';
  (scenarios || []).forEach((scenario) => {
    const row = document.createElement('tr');
    row.innerHTML = `<td>${escapeHtml(scenario.scenario_name || scenario.name || '')}</td><td>${formatCurrencyValue(scenario.price_low, 'USD')}</td><td>${formatCurrencyValue(scenario.price_mid, 'USD')}</td><td>${formatCurrencyValue(scenario.price_high, 'USD')}</td><td>${formatPercent(scenario.cagr_low)}</td><td>${formatPercent(scenario.cagr_mid)}</td><td>${formatPercent(scenario.cagr_high)}</td><td>${formatPercent((scenario.probability || 0) * 100)}</td>`;
    targetBody.appendChild(row);
  });
}

function buildScenarioTableHtml(scenarios) {
  const rows = (scenarios || []).map((scenario) => `<tr><td>${escapeHtml(scenario.scenario_name || scenario.name || '')}</td><td>${formatCurrencyValue(scenario.price_low, 'USD')}</td><td>${formatCurrencyValue(scenario.price_mid, 'USD')}</td><td>${formatCurrencyValue(scenario.price_high, 'USD')}</td><td>${formatPercent(scenario.cagr_low)}</td><td>${formatPercent(scenario.cagr_mid)}</td><td>${formatPercent(scenario.cagr_high)}</td><td>${formatPercent((scenario.probability || 0) * 100)}</td></tr>`).join('');
  return `<div class="table-wrap"><table class="scenario-overlay-table"><thead><tr><th>Scenario</th><th>Price Low</th><th>Price Mid</th><th>Price High</th><th>CAGR Low</th><th>CAGR Mid</th><th>CAGR High</th><th>Probability</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function setScenarioOverlayTab(tab) {
  activeScenarioOverlayTab = tab;
  renderScenarioOverlayArea();
}

function renderScenarioOverlayArea() {
  const hasExternal = hasExternalScenarioOverlay();
  if (!hasExternal) activeScenarioOverlayTab = 'bakingmoney';
  else if (!['final', 'bakingmoney', 'external'].includes(activeScenarioOverlayTab)) activeScenarioOverlayTab = 'final';

  analysisScenarioOverlayTabsEl.classList.toggle('hidden', !hasExternal);
  analysisFinalScenarioPanelEl.classList.toggle('hidden', !hasExternal || activeScenarioOverlayTab !== 'final');
  analysisExternalScenariosPanelEl.classList.toggle('hidden', !hasExternal || activeScenarioOverlayTab !== 'external');
  analysisBakingMoneyScenarioPanelEl.classList.toggle('hidden', hasExternal && activeScenarioOverlayTab !== 'bakingmoney');
  analysisAddExternalScenarioBtn.classList.toggle('hidden', hasExternal && activeScenarioOverlayTab !== 'external');
  analysisScenarioOverlayTabButtons.forEach((button) => {
    const active = button.dataset.scenarioTab === activeScenarioOverlayTab;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', active ? 'true' : 'false');
  });

  renderScenarioRows(analysisDetailState?.version?.scenarios || []);
  if (hasExternal) {
    renderFinalScenarioPanel();
    renderExternalScenariosPanel();
  }
  updateAnalysisScenarioInfoText();
}

function renderFinalScenarioPanel() {
  const overlay = analysisDetailState?.final_scenario_overlay;
  if (!overlay) {
    analysisFinalScenarioPanelEl.innerHTML = '<p class="status warning">Final Scenario has not been recalculated yet.</p><button type="button" class="final-scenario-recalculate-btn">Recalculate Final Scenario</button>';
    return;
  }
  const stale = overlay.is_stale || analysisDetailState?.final_scenario_stale;
  const warning = stale ? '<p class="status warning">External scenarios changed. Recalculate Final Scenario to apply the latest weights and scenario values.</p>' : '';
  analysisFinalScenarioPanelEl.innerHTML = `${warning}<div class="summary-grid scenario-overlay-summary"><div class="summary-item"><div class="label">Final Expected Price</div><div class="value">${formatCurrencyValue(overlay.expected_price, 'USD')}</div></div><div class="summary-item"><div class="label">Final Expected CAGR</div><div class="value ${valueClass(overlay.expected_cagr)}">${formatPercent(overlay.expected_cagr)}</div></div><div class="summary-item"><div class="label">Final Upside</div><div class="value ${valueClass(overlay.upside)}">${formatPercent(overlay.upside)}</div></div><div class="summary-item"><div class="label">BakingMoney Weight</div><div class="value">${formatPercent(overlay.bakingmoney_weight_percent)}</div></div><div class="summary-item"><div class="label">External Weight</div><div class="value">${formatPercent(overlay.external_total_weight_percent)}</div></div><div class="summary-item"><div class="label">Last Recalculated</div><div class="value">${formatDateTime(overlay.recalculated_at)}</div></div></div>${buildScenarioTableHtml(overlay.scenarios)}<div class="table-actions"><button type="button" class="final-scenario-recalculate-btn">Recalculate Final Scenario</button></div>`;
}

function getPendingExternalWeightTotalPercent() {
  let total = 0;
  analysisExternalScenariosPanelEl.querySelectorAll('.external-scenario-weight-input').forEach((input) => {
    const value = Number(input.value);
    if (Number.isFinite(value)) total += value;
  });
  return total;
}

function updateExternalWeightSummary() {
  const total = getPendingExternalWeightTotalPercent();
  const bakingWeight = 100 - total;
  const warning = analysisExternalScenariosPanelEl.querySelector('.external-weight-warning');
  const summary = analysisExternalScenariosPanelEl.querySelector('.external-weight-summary');
  if (summary) summary.textContent = `Pending external weight: ${formatPercent(total)} • Pending BakingMoney weight: ${formatPercent(bakingWeight)}`;
  if (warning) {
    warning.textContent = total > 100 ? 'External scenario weights total more than 100%. Reduce weights before recalculating.' : '';
    warning.classList.toggle('hidden', total <= 100);
  }
}

function renderExternalScenariosPanel() {
  const items = getCurrentExternalScenarios();
  const currentTotal = items.reduce((total, item) => total + externalScenarioWeightPercent(item), 0);
  const cards = items.map((item) => `<section class="external-scenario-card" data-external-id="${item.id}"><div class="view-header"><h4>${escapeHtml(item.title)}</h4><div class="table-actions"><button type="button" class="external-scenario-edit-btn" data-external-id="${item.id}">Edit</button><button type="button" class="external-scenario-remove-btn remove-btn" data-external-id="${item.id}">Remove</button></div></div><label class="external-scenario-weight-label">Weight (%) <input class="external-scenario-weight-input" data-external-id="${item.id}" type="number" min="0" max="100" step="0.1" value="${externalScenarioWeightPercent(item)}"></label>${item.source_notes ? `<p class="external-scenario-notes">${escapeHtml(item.source_notes)}</p>` : ''}${buildScenarioTableHtml(item.scenarios)}</section>`).join('');
  analysisExternalScenariosPanelEl.innerHTML = `<div class="external-scenario-actions"><p class="status external-weight-summary">Pending external weight: ${formatPercent(currentTotal)} • Pending BakingMoney weight: ${formatPercent(100 - currentTotal)}</p><p class="status error external-weight-warning hidden"></p><div class="table-actions"><button type="button" id="analysis-external-add-another-btn">Add External Scenario</button><button type="button" id="analysis-external-recalculate-btn">Recalculate Final Scenario</button></div></div>${cards || '<p class="status">No external scenarios.</p>'}`;
  analysisExternalScenariosPanelEl.querySelectorAll('.external-scenario-weight-input').forEach((input) => input.addEventListener('input', updateExternalWeightSummary));
  updateExternalWeightSummary();
}

function externalScenarioPayloadFromItemWithWeight(item, weightPercent) {
  return {
    title: item.title,
    external_weight: weightPercent,
    source_notes: item.source_notes || '',
    scenario_json: item.scenario_json || JSON.stringify({ scenarios: item.scenarios }, null, 2),
  };
}

async function savePendingExternalWeights() {
  const updates = [];
  for (const input of analysisExternalScenariosPanelEl.querySelectorAll('.external-scenario-weight-input')) {
    const id = Number(input.dataset.externalId);
    const item = getCurrentExternalScenarios().find((scenario) => Number(scenario.id) === id);
    if (!item) continue;
    const weight = Number(input.value);
    if (!Number.isFinite(weight) || weight < 0 || weight > 100) throw new Error('Each external scenario weight must be between 0% and 100%.');
    if (Math.abs(weight - externalScenarioWeightPercent(item)) > 0.0001) {
      updates.push(fetch(`/api/analysis/versions/${encodeURIComponent(analysisDetailState.selected_version_id)}/external-scenarios/${encodeURIComponent(id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(externalScenarioPayloadFromItemWithWeight(item, weight)),
      }).then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to save external scenario weight'));
        return payload;
      }));
    }
  }
  if (updates.length) await Promise.all(updates);
}


async function refreshAnalysisDetailAfterExternalScenarioChange(targetTab = null) {
  const symbol = analysisDetailState?.symbol;
  const versionId = analysisDetailState?.selected_version_id;
  if (!symbol || !versionId) return;
  await loadAnalysisDetail(symbol, versionId);
  if (targetTab) {
    activeScenarioOverlayTab = targetTab;
    renderScenarioOverlayArea();
  }
}

async function recalculateFinalScenario() {
  analysisDetailStatus.textContent = 'Recalculating final scenario…';
  analysisDetailStatus.className = 'status';
  try {
    await savePendingExternalWeights();
    const response = await fetch(`/api/analysis/versions/${encodeURIComponent(analysisDetailState.selected_version_id)}/final-scenario/recalculate`, { method: 'POST' });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to recalculate final scenario'));
    Object.assign(analysisDetailState, payload);
    await refreshAnalysisDetailAfterExternalScenarioChange('final');
    analysisDetailStatus.textContent = 'Final Scenario recalculated.';
    analysisDetailStatus.className = 'status';
  } catch (error) {
    analysisDetailStatus.textContent = `Error: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

function openExternalScenarioModal(item = null) {
  editingExternalScenarioId = item?.id || null;
  analysisExternalScenarioModalTitleEl.textContent = item ? 'Edit External Scenario' : 'Add External Scenario';
  analysisExternalScenarioTitleEl.value = item?.title || '';
  analysisExternalScenarioWeightEl.value = item ? externalScenarioWeightPercent(item) : 30;
  analysisExternalScenarioNotesEl.value = item ? (item.source_notes || '') : formatLocalDateForExternalScenarioNotes();
  analysisExternalScenarioJsonEl.value = item?.scenario_json || getExternalScenarioTemplate();
  analysisExternalScenarioStatusEl.textContent = '';
  analysisExternalScenarioStatusEl.className = 'status';
  analysisExternalScenarioModalEl.classList.remove('hidden');
  analysisExternalScenarioTitleEl.focus();
}

function closeExternalScenarioModal() {
  editingExternalScenarioId = null;
  analysisExternalScenarioModalEl.classList.add('hidden');
}

async function saveExternalScenarioFromModal() {
  const versionId = analysisDetailState?.selected_version_id;
  if (!versionId) return;
  const payload = {
    title: analysisExternalScenarioTitleEl.value,
    external_weight: analysisExternalScenarioWeightEl.value,
    source_notes: analysisExternalScenarioNotesEl.value,
    scenario_json: analysisExternalScenarioJsonEl.value,
  };
  analysisExternalScenarioStatusEl.textContent = 'Saving external scenario…';
  analysisExternalScenarioStatusEl.className = 'status';
  const url = editingExternalScenarioId
    ? `/api/analysis/versions/${encodeURIComponent(versionId)}/external-scenarios/${encodeURIComponent(editingExternalScenarioId)}`
    : `/api/analysis/versions/${encodeURIComponent(versionId)}/external-scenarios`;
  try {
    const response = await fetch(url, {
      method: editingExternalScenarioId ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(result, 'Unable to save external scenario'));
    Object.assign(analysisDetailState, result);
    closeExternalScenarioModal();
    await refreshAnalysisDetailAfterExternalScenarioChange('external');
    analysisDetailStatus.textContent = 'External scenario saved. Recalculate Final Scenario to apply it.';
    analysisDetailStatus.className = 'status';
  } catch (error) {
    analysisExternalScenarioStatusEl.textContent = `Error: ${error.message}`;
    analysisExternalScenarioStatusEl.className = 'status error';
  }
}

async function removeExternalScenario(id) {
  if (!window.confirm('Remove this external scenario?')) return;
  analysisDetailStatus.textContent = 'Removing external scenario…';
  analysisDetailStatus.className = 'status';
  try {
    const response = await fetch(`/api/analysis/versions/${encodeURIComponent(analysisDetailState.selected_version_id)}/external-scenarios/${encodeURIComponent(id)}`, { method: 'DELETE' });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to remove external scenario'));
    Object.assign(analysisDetailState, payload);
    const hasRemainingExternalScenarios = hasExternalScenarioOverlay();
    await refreshAnalysisDetailAfterExternalScenarioChange(hasRemainingExternalScenarios ? 'external' : 'bakingmoney');
    analysisDetailStatus.textContent = hasRemainingExternalScenarios ? 'External scenario removed. Recalculate Final Scenario to apply the change.' : 'External scenario removed.';
    analysisDetailStatus.className = 'status';
  } catch (error) {
    analysisDetailStatus.textContent = `Error: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

function buildExternalScenarioInfoText() {
  const items = getCurrentExternalScenarios();
  if (!items.length) return '\n\nExternal Scenario Overlay:\n- No external scenarios attached to this version.';
  const overlay = analysisDetailState.final_scenario_overlay;
  const status = overlay ? (overlay.is_stale ? 'Stale' : 'Recalculated') : 'Not recalculated';
  const lines = [
    '\n\nExternal Scenario Overlay:',
    `- Final Scenario status: ${status}`,
  ];
  if (overlay?.recalculated_at) lines.push(`- Last recalculated: ${formatDateTime(overlay.recalculated_at)}`);
  if (overlay) {
    lines.push(`- BakingMoney weight from last recalculation: ${formatPercent(overlay.bakingmoney_weight_percent)}`);
    lines.push(`- External total weight from last recalculation: ${formatPercent(overlay.external_total_weight_percent)}`);
  }
  lines.push('- External scenarios:');
  items.forEach((item) => lines.push(`  - ${item.title}: ${formatPercent(externalScenarioWeightPercent(item))}, updated ${formatDateTime(item.updated_at)}`));
  if (overlay?.is_stale) lines.push('- Final Scenario may not reflect latest external scenario changes.');
  return lines.join('\n');
}

function updateAnalysisScenarioInfoText() {
  const item = analysisDetailState?.version;
  if (!item) return;
  const passes = item.scenario_passes || [];
  const passLines = passes.map((p) => `Pass ${p.pass_index}: status=${p.validation_status}${p.is_outlier ? ' outlier=true' : ''}${p.rejection_reason ? ` reason=${p.rejection_reason}` : ''}${typeof p.quality_score === 'number' ? ` score=${p.quality_score.toFixed(2)}` : ''}`);
  analysisScenarioInfoText.textContent = `Prompt used to build scenarios:\n${item.scenario_prompt || 'N/A'}\n\nScenario build passes:\n${passLines.length ? passLines.join('\n') : 'No pass details available.'}${buildExternalScenarioInfoText()}`;
}


function renderVersionControls() {
  if (!analysisDetailState) return;
  const versions = analysisDetailState.versions || [];
  const idx = selectedVersionIndex();
  analysisVersionBar.classList.remove('hidden');
  analysisVersionSelect.innerHTML = '';
  versions.forEach((version) => {
    const opt = document.createElement('option');
    opt.value = version.id;
    opt.textContent = `V${version.version_number} • ${formatDateTime(version.created_at)}`;
    analysisVersionSelect.appendChild(opt);
  });
  analysisVersionSelect.value = String(analysisDetailState.selected_version_id);
  analysisVersionPrevBtn.disabled = idx <= 0;
  analysisVersionNextBtn.disabled = idx >= versions.length - 1;
  const current = versions[idx];
  analysisVersionMeta.textContent = current ? `Version ${current.version_number} created ${formatDateTime(current.created_at)} (${current.source_trigger || 'unknown'})` : '';
}

function renderAnalysisDetail() {
  const item = analysisDetailState.version;
  analysisDetailTitle.textContent = `Analysis: ${analysisDetailState.symbol}`;
  const effectiveBusinessModel = getEffectiveBusinessModel();
  const effectiveBusinessSummary = getEffectiveBusinessSummary();
  const safeBusinessModel = escapeHtml(effectiveBusinessModel);
  const safeBusinessSummary = escapeHtml(effectiveBusinessSummary);
  const safeAssumptions = escapeHtml(item.assumptions || '');
  const businessModelSection = isEditingBusinessModel
    ? `<div class="business-model-editor"><label><strong>Business Model:</strong></label><textarea id="analysis-business-model-input" class="analysis-business-model-input" rows="5">${safeBusinessModel}</textarea><div class="table-actions"><button id="analysis-business-model-save-btn">Save</button><button id="analysis-business-model-cancel-btn">Cancel</button></div></div>`
    : `<div class="business-model-editor"><p><strong>Business Model:</strong> ${safeBusinessModel || 'N/A'}</p><div class="table-actions"><button id="analysis-business-model-edit-btn">Edit Business Model</button></div></div>`;
  const businessSummarySection = isEditingBusinessSummary
    ? `<div class="business-model-editor"><label><strong>Business Summary:</strong></label><textarea id="analysis-business-summary-input" class="analysis-business-model-input" rows="4">${safeBusinessSummary}</textarea><div class="table-actions"><button id="analysis-business-summary-save-btn">Save</button><button id="analysis-business-summary-cancel-btn">Cancel</button></div></div>`
    : `<div class="business-model-editor"><p><strong>Business Summary:</strong> ${safeBusinessSummary || 'N/A'}</p><div class="table-actions"><button id="analysis-business-summary-edit-btn">Edit Business Summary</button></div></div>`;
  const frontierOptionalitySection = renderFrontierOptionalitySection();
  const releaseSummaryCard = renderAnalysisReleaseSummaryCard();
  analysisSummary.innerHTML = `<div class="summary-grid"><div class="summary-item"><div class="label">Symbol</div><div class="value">${item.symbol}</div></div><div class="summary-item"><div class="label">Company Name</div><div class="value">${item.company_name || 'N/A'}</div></div><div class="summary-item"><div class="label">Current Price</div><div class="value">${formatCurrencyValue(item.current_price, 'USD')}</div></div><div class="summary-item"><div class="label">Expected Price</div><div class="value">${formatCurrencyValue(item.expected_price, 'USD')}</div></div><div class="summary-item"><div class="label">Expected CAGR</div><div class="value ${valueClass(item.expected_cagr)}">${formatPercent(item.expected_cagr)}</div></div><div class="summary-item"><div class="label">Upside</div><div class="value ${valueClass(item.upside)}">${formatPercent(item.upside)}</div></div><div class="summary-item"><div class="label">Confidence</div><div class="value confidence-breakdown"><div>Core: ${formatCoreConfidenceDisplay(item)}</div><div>Potential: ${formatPotentialConfidenceDisplay(item)}</div></div></div>${releaseSummaryCard}<div class="summary-item"><div class="label">Rating</div><div class="value">${item.rating || 'Hold'}</div></div><div class="summary-item" title="Short-term technical momentum calculated from TWS historical price and volume data."><div class="label">Momentum</div><div class="value">${formatMomentumSummaryValue(item.momentum_score, item.momentum_label)}</div></div><div class="summary-item" title="Measures whether the stock appears technically extended based on price distance from trend, recent return, and volatility."><div class="label">Extension Risk</div><div class="value">${formatMomentumSummaryValue(item.extension_risk, item.extension_label)}</div></div></div>${businessModelSection}${businessSummarySection}${frontierOptionalitySection}<p><strong>Assumptions:</strong> ${safeAssumptions || 'N/A'}</p>`;
  analysisSummary.classList.remove('hidden');

  renderScenarioOverlayArea();

  renderVariablesTable();
  renderVersionControls();
  analysisRerunBtn.disabled = false;

  updateAnalysisScenarioInfoText();
}

function getCurrentAnalysisKeyVariables() {
  const hasSavedEditsForVersion = analysisDetailState.saved_key_variable_edits?.based_on_version_id === analysisDetailState.version.id;
  return hasSavedEditsForVersion
    ? analysisDetailState.saved_key_variable_edits.key_variables || []
    : analysisDetailState.version.key_variables || [];
}

function numberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function probabilityToPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return Math.abs(number) <= 1 ? Number((number * 100).toFixed(2)) : Number(number.toFixed(2));
}

function normalizeCopiedKeyVariable(variable = {}) {
  return {
    variable: variable.variable_text || variable.variable || '',
    type: variable.variable_type || variable.type || 'Bullish',
    driver_category: normalizeDriverCategory(variable.driver_category),
    confidence: numberOrNull(variable.confidence),
    importance: numberOrNull(variable.importance),
  };
}

function buildCopiedConfidence(item) {
  const core = getCoreConfidenceFields(item);
  const coreBullish = numberOrNull(core.bullish);
  const coreBearish = numberOrNull(core.bearish);
  const potentialBullish = numberOrNull(item?.potential_bullish_confidence);
  const potentialBearish = numberOrNull(item?.potential_bearish_confidence);
  return {
    core: {
      net: numberOrNull(core.diff) ?? (coreBullish !== null && coreBearish !== null ? Number((coreBullish - coreBearish).toFixed(2)) : null),
      bullish: coreBullish,
      bearish: coreBearish,
    },
    potential: {
      net: numberOrNull(item?.potential_confidence_diff) ?? (potentialBullish !== null && potentialBearish !== null ? Number((potentialBullish - potentialBearish).toFixed(2)) : null),
      bullish: potentialBullish,
      bearish: potentialBearish,
    },
  };
}

function normalizeCopiedScenario(scenario = {}) {
  return {
    name: scenario.scenario_name || scenario.name || '',
    price_low: numberOrNull(scenario.price_low),
    price_mid: numberOrNull(scenario.price_mid),
    price_high: numberOrNull(scenario.price_high),
    probability: probabilityToPercent(scenario.probability),
  };
}

function getCopiedScenarioSummary(item) {
  const overlay = analysisDetailState?.final_scenario_overlay;
  const useFinal = Boolean(overlay);
  const scenarios = useFinal ? overlay.scenarios : item.scenarios;
  return {
    source: useFinal ? 'Final Scenario Overlay' : 'BakingMoney Scenario',
    is_stale: useFinal ? Boolean(overlay.is_stale) : false,
    bakingmoney_weight: useFinal ? numberOrNull(overlay.bakingmoney_weight_percent) : 100,
    external_weight: useFinal ? numberOrNull(overlay.external_total_weight_percent) : 0,
    final_expected_price: numberOrNull(useFinal ? overlay.expected_price : item.expected_price),
    final_expected_cagr: numberOrNull(useFinal ? overlay.expected_cagr : item.expected_cagr),
    final_upside: numberOrNull(useFinal ? overlay.upside : item.upside),
    last_recalculated: useFinal ? overlay.recalculated_at || null : null,
    scenarios: (scenarios || []).map(normalizeCopiedScenario),
  };
}

function buildCompanyReviewData() {
  const item = analysisDetailState?.version;
  if (!item) return null;
  const release = getSelectedAnalysisReleaseEntry();
  const scenarioSummary = getCopiedScenarioSummary(item);
  return {
    company_context: {
      symbol: item.symbol || analysisDetailState?.symbol || null,
      company_name: item.company_name || null,
      version: item.version_number ?? analysisDetailState?.selected_version_id ?? null,
      created_at: item.created_at || null,
      business_model: getEffectiveBusinessModel() || null,
      business_summary: getEffectiveBusinessSummary() || null,
      assumptions: item.assumptions || null,
    },
    model_summary: {
      current_price: numberOrNull(item.current_price),
      expected_price: numberOrNull(item.expected_price),
      expected_cagr: numberOrNull(item.expected_cagr),
      upside: numberOrNull(item.upside),
      rating: item.rating || null,
      earnings_release: release ? formatAnalysisReleaseEntry(release) : null,
      last_recalculated: scenarioSummary.last_recalculated,
    },
    confidence: buildCopiedConfidence(item),
    scenario_summary: scenarioSummary,
    key_variables: getCurrentAnalysisKeyVariables().map(normalizeCopiedKeyVariable),
  };
}

function buildKeyVariablesCopyPayload() {
  const item = analysisDetailState?.version;
  if (!item) return null;
  return {
    symbol: item.symbol || analysisDetailState?.symbol || null,
    company_name: item.company_name || null,
    version: item.version_number ?? analysisDetailState?.selected_version_id ?? null,
    created_at: item.created_at || null,
    rating: item.rating || null,
    current_price: numberOrNull(item.current_price),
    expected_price: numberOrNull(item.expected_price),
    upside: numberOrNull(item.upside),
    expected_cagr: numberOrNull(item.expected_cagr),
    confidence: buildCopiedConfidence(item),
    key_variables: getCurrentAnalysisKeyVariables().map(normalizeCopiedKeyVariable),
  };
}

function buildReviewPromptText() {
  const data = buildCompanyReviewData();
  if (!data) return '';
  return `Review this company for BakingMoney.

Please check whether the key variables are specific, non-overlapping, material over a 5-year horizon, correctly classified as Core/Potential and Bullish/Bearish, and useful for scenario building. Also check whether the current 5-year scenario and rating make sense based on the company trajectory, risks, valuation, and the key variables.

If changes are needed:

1. Identify the strongest variables.
2. Identify weak, overlapping, or secondary variables.
3. Explain any missing risks or drivers.
4. Provide a revised full key-variable JSON.
5. If the scenario should be changed, provide an improved external scenario JSON using only name, price_low, price_high, and probability.

Company data:
\`\`\`json
${JSON.stringify(data, null, 2)}
\`\`\``;
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  const ok = document.execCommand('copy');
  document.body.removeChild(textarea);
  if (!ok) throw new Error('Clipboard copy was not available.');
}

async function copyAnalysisKeyVariablesJson() {
  const payload = buildKeyVariablesCopyPayload();
  if (!payload) return;
  try {
    await copyTextToClipboard(JSON.stringify(payload, null, 2));
    analysisDetailStatus.textContent = 'Copied key variables JSON to clipboard.';
    analysisDetailStatus.className = 'status';
  } catch (error) {
    analysisDetailStatus.textContent = `Error copying key variables JSON: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

async function copyAnalysisReviewPrompt() {
  const prompt = buildReviewPromptText();
  if (!prompt) return;
  try {
    await copyTextToClipboard(prompt);
    analysisDetailStatus.textContent = 'Copied review prompt to clipboard.';
    analysisDetailStatus.className = 'status';
  } catch (error) {
    analysisDetailStatus.textContent = `Error copying review prompt: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

function normalizeAnalysisVariableForUi(variable = {}) {
  return {
    variable_text: variable.variable_text || '',
    variable_type: variable.variable_type === 'Bearish' ? 'Bearish' : 'Bullish',
    driver_category: normalizeDriverCategory(variable.driver_category),
    confidence: Number.isFinite(Number(variable.confidence)) ? Number(variable.confidence) : 0,
    importance: Number.isFinite(Number(variable.importance)) ? Number(variable.importance) : 0,
  };
}

function getAnalysisVariableEditDraft() {
  if (!editableAnalysisVariables) {
    editableAnalysisVariables = getCurrentAnalysisKeyVariables().map(normalizeAnalysisVariableForUi);
  }
  return editableAnalysisVariables;
}

function syncActiveAnalysisVariableRowsFromDom() {
  if (!isEditingVariables || !editableAnalysisVariables) return;
  analysisVariablesBody.querySelectorAll('tr[data-variable-index]').forEach((row) => {
    const index = Number(row.dataset.variableIndex);
    if (!Number.isInteger(index) || !editableAnalysisVariables[index]) return;
    editableAnalysisVariables[index] = {
      variable_text: row.querySelector('.var-text')?.value?.trim() || '',
      variable_type: row.querySelector('.var-type')?.value === 'Bearish' ? 'Bearish' : 'Bullish',
      driver_category: normalizeDriverCategory(row.querySelector('.var-driver-category')?.value),
      confidence: Number(row.querySelector('.var-confidence')?.value),
      importance: Number(row.querySelector('.var-importance')?.value),
    };
  });
}

function updateAnalysisVariableTabs(variables) {
  const counts = variables.reduce((acc, variable) => {
    const category = normalizeDriverCategory(variable.driver_category);
    acc[category] = (acc[category] || 0) + 1;
    return acc;
  }, { 'Core Driver': 0, 'Potential Driver': 0 });

  analysisVariableTabButtons.forEach((button) => {
    const category = normalizeDriverCategory(button.dataset.driverCategory);
    const isActive = category === activeAnalysisVariableCategory;
    const label = category === 'Potential Driver' ? 'Potential Drivers' : 'Core Drivers';
    button.textContent = `${label} (${counts[category] || 0})`;
    button.classList.toggle('active', isActive);
    button.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });
}

function renderVariablesTable() {
  const variables = isEditingVariables
    ? getAnalysisVariableEditDraft()
    : getCurrentAnalysisKeyVariables().map(normalizeAnalysisVariableForUi);
  const activeCategory = normalizeDriverCategory(activeAnalysisVariableCategory);
  activeAnalysisVariableCategory = activeCategory;
  const visibleVariables = variables
    .map((variable, index) => ({ variable: normalizeAnalysisVariableForUi(variable), index }))
    .filter(({ variable }) => normalizeDriverCategory(variable.driver_category) === activeCategory);

  updateAnalysisVariableTabs(variables);
  analysisVariablesBody.innerHTML = '';
  visibleVariables.forEach(({ variable, index }) => {
    const row = document.createElement('tr');
    row.dataset.variableIndex = String(index);
    const variableType = variable.variable_type || 'Bullish';
    const driverCategory = normalizeDriverCategory(variable.driver_category);
    row.innerHTML = isEditingVariables
      ? `<td><input class="var-text var-text-input" type="text" value="${escapeHtml(variable.variable_text || '')}"></td><td><select class="var-type"><option value="Bullish" ${variableType === 'Bullish' ? 'selected' : ''}>Bullish</option><option value="Bearish" ${variableType === 'Bearish' ? 'selected' : ''}>Bearish</option></select></td><td>${renderDriverCategorySelect('var-driver-category', driverCategory)}</td><td><input class="var-confidence" type="number" min="0" max="10" step="1" value="${variable.confidence}"></td><td><input class="var-importance" type="number" min="0" max="10" step="1" value="${variable.importance}"></td><td><button type="button" class="var-delete-btn remove-btn">Delete</button></td>`
      : `<td>${escapeHtml(variable.variable_text || '')}</td><td>${escapeHtml(variableType)}</td><td>${escapeHtml(driverCategory)}</td><td>${formatNumber(variable.confidence, 2)}</td><td>${formatNumber(variable.importance, 2)}</td><td>—</td>`;
    analysisVariablesBody.appendChild(row);
  });

  if (analysisVariablesEmptyEl) {
    const emptyLabel = activeCategory === 'Potential Driver' ? 'Potential Driver' : 'Core Driver';
    analysisVariablesEmptyEl.textContent = `No ${emptyLabel} variables.`;
    analysisVariablesEmptyEl.classList.toggle('hidden', visibleVariables.length > 0);
  }

  if (isEditingVariables) {
    analysisVariablesBody.querySelectorAll('.var-delete-btn').forEach((button) => {
      button.addEventListener('click', () => {
        syncActiveAnalysisVariableRowsFromDom();
        const index = Number(button.closest('tr')?.dataset.variableIndex);
        if (Number.isInteger(index)) editableAnalysisVariables.splice(index, 1);
        renderVariablesTable();
      });
    });
    analysisVariablesBody.querySelectorAll('.var-driver-category').forEach((select) => {
      select.addEventListener('change', () => {
        syncActiveAnalysisVariableRowsFromDom();
        renderVariablesTable();
      });
    });
  }

  analysisEditVariablesBtn.classList.toggle('hidden', isEditingVariables);
  analysisAddVariableBtn.classList.toggle('hidden', !isEditingVariables);
  analysisSaveVariablesBtn.classList.toggle('hidden', !isEditingVariables);
  analysisCancelVariablesBtn.classList.toggle('hidden', !isEditingVariables);
}

async function openAnalysisDetailForSymbol(symbol, options = {}) {
  const origin = ['positions', 'action_plan', 'earnings_review'].includes(options.origin) ? options.origin : 'analysis';
  analysisDetailOrigin = origin;

  if (origin === 'positions') {
    showAnalysisDetailFromPositionsOrigin();
  } else if (origin === 'action_plan') {
    showAnalysisDetailFromActionPlanOrigin();
  } else if (origin === 'earnings_review') {
    showAnalysisDetailFromEarningsReviewOrigin();
  } else {
    setView('analysis');
  }

  await loadAnalysisDetail(symbol);
}

async function openAnalysisDetailFromPositions(symbol) {
  analysisDetailOrigin = 'positions';
  showAnalysisDetailFromPositionsOrigin();
  await loadAnalysisDetail(symbol);
}

async function loadAnalysisDetail(symbol, versionId = null) {
  analysisDetailStatus.textContent = `Loading ${symbol} detail…`;
  analysisDetailStatus.className = 'status';
  analysisSummary.classList.add('hidden');
  analysisListView.classList.add('hidden');
  analysisDetailView.classList.remove('hidden');
  if (analysisDetailOrigin === 'positions') showAnalysisDetailFromPositionsOrigin();
  if (analysisDetailOrigin === 'action_plan') showAnalysisDetailFromActionPlanOrigin();
  if (analysisDetailOrigin === 'earnings_review') showAnalysisDetailFromEarningsReviewOrigin();
  updateAnalysisBackButton();
  isEditingVariables = false;
  activeAnalysisVariableCategory = 'Core Driver';
  editableAnalysisVariables = null;
  isEditingBusinessModel = false;
  isEditingBusinessSummary = false;

  try {
    const query = versionId ? `?version_id=${encodeURIComponent(versionId)}` : '';
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}${query}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load details'));
    analysisDetailState = payload.analysis;
    analysisDetailState.selected_release_index = 0;
    activeScenarioOverlayTab = hasExternalScenarioOverlay() ? 'final' : 'bakingmoney';
    renderAnalysisDetail();
    analysisDetailStatus.textContent = `Loaded ${symbol} detail.`;
  } catch (error) {
    const noAnalysisMessage = 'No analysis found for this symbol.';
    analysisDetailStatus.textContent = /not found/i.test(error.message || '') ? noAnalysisMessage : `Error: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

function collectEditedVariables() {
  syncActiveAnalysisVariableRowsFromDom();
  return getAnalysisVariableEditDraft().map(normalizeAnalysisVariableForUi);
}

async function saveEditedBusinessModel() {
  const symbol = analysisDetailState.symbol;
  const versionId = analysisDetailState.version.id;
  const businessModel = document.getElementById('analysis-business-model-input')?.value?.trim() || '';
  if (!businessModel) {
    analysisDetailStatus.textContent = 'Business model cannot be empty.';
    analysisDetailStatus.className = 'status error';
    return;
  }

  analysisDetailStatus.textContent = 'Saving business model edit…';
  analysisDetailStatus.className = 'status';
  try {
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}/business-model`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version_id: versionId, business_model: businessModel }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to save business model'));
    analysisDetailState = payload.analysis;
    isEditingBusinessModel = false;
    renderAnalysisDetail();
    analysisDetailStatus.textContent = 'Business model edit saved.';
  } catch (error) {
    analysisDetailStatus.textContent = `Error: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

function cancelEditedBusinessModel() {
  isEditingBusinessModel = false;
  renderAnalysisDetail();
  analysisDetailStatus.textContent = 'Business model editing canceled.';
  analysisDetailStatus.className = 'status';
}

async function saveEditedBusinessSummary() {
  const symbol = analysisDetailState.symbol;
  const versionId = analysisDetailState.version.id;
  const businessSummary = document.getElementById('analysis-business-summary-input')?.value?.trim() || '';

  analysisDetailStatus.textContent = 'Saving business summary edit…';
  analysisDetailStatus.className = 'status';
  try {
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}/business-summary`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version_id: versionId, business_summary: businessSummary }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to save business summary'));
    analysisDetailState = payload.analysis;
    isEditingBusinessSummary = false;
    renderAnalysisDetail();
    analysisDetailStatus.textContent = 'Business summary edit saved.';
  } catch (error) {
    analysisDetailStatus.textContent = `Error: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

function cancelEditedBusinessSummary() {
  isEditingBusinessSummary = false;
  renderAnalysisDetail();
  analysisDetailStatus.textContent = 'Business summary editing canceled.';
  analysisDetailStatus.className = 'status';
}

function getCurrentFrontierOptionality() {
  const payload = analysisDetailState?.frontier_optionality || {};
  const score = Number(payload.frontier_optionality_score ?? analysisDetailState?.version?.frontier_optionality_score ?? 0);
  return {
    score: Number.isFinite(score) ? score : 0,
  };
}

function normalizeFrontierScoreForSelect(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  const bounded = Math.min(5, Math.max(0, number));
  return Math.round(bounded * 2) / 2;
}

function formatFrontierScoreOption(value) {
  return Number.isInteger(value) ? String(value) : String(value);
}

function renderFrontierScoreOptions(selectedScore) {
  const selected = normalizeFrontierScoreForSelect(selectedScore);
  return FRONTIER_SCORE_OPTIONS.map((value) => {
    const text = formatFrontierScoreOption(value);
    return `<option value="${text}"${value === selected ? ' selected' : ''}>${text}</option>`;
  }).join('');
}

function renderFrontierOptionalitySection() {
  const frontier = getCurrentFrontierOptionality();
  return `<div class="business-model-editor frontier-score-field"><label for="analysis-frontier-score-select"><strong>Frontier Score</strong></label><select id="analysis-frontier-score-select" class="earnings-calendar-select">${renderFrontierScoreOptions(frontier.score)}</select></div>`;
}

async function saveFrontierScore(rawScore) {
  const symbol = analysisDetailState.symbol;
  const score = rawScore === '' ? 0 : Number(rawScore);
  if (!Number.isFinite(score) || score < 0 || score > 5) {
    analysisDetailStatus.textContent = 'Frontier Score must be between 0 and 5.';
    analysisDetailStatus.className = 'status error';
    return;
  }

  analysisDetailStatus.textContent = 'Saving Frontier Score...';
  analysisDetailStatus.className = 'status';
  try {
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}/frontier-optionality`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ frontier_optionality_score: score }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to save Frontier Score'));
    analysisDetailState = payload.analysis;
    renderAnalysisDetail();
    analysisDetailStatus.textContent = 'Frontier Score saved.';
  } catch (error) {
    analysisDetailStatus.textContent = `Error: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

function getKeyVariableImportTemplate() {
  return JSON.stringify({
    symbol: analysisDetailState?.symbol || 'SYMBOL',
    key_variables: [
      {
        variable: 'Example bullish core driver',
        type: 'Bullish',
        driver_category: 'Core Driver',
        confidence: 7,
        importance: 8,
      },
      {
        variable: 'Example bearish potential risk',
        type: 'Bearish',
        driver_category: 'Potential Driver',
        confidence: 4,
        importance: 7,
      },
    ],
  }, null, 2);
}

function openKeyVariableImportModal() {
  analysisKeyVariableImportJsonEl.value = getKeyVariableImportTemplate();
  analysisKeyVariableImportStatusEl.textContent = '';
  analysisKeyVariableImportStatusEl.className = 'status';
  analysisKeyVariableImportModalEl.classList.remove('hidden');
  analysisKeyVariableImportJsonEl.focus();
}

function closeKeyVariableImportModal() {
  analysisKeyVariableImportModalEl.classList.add('hidden');
}

function parseKeyVariableImportPayload() {
  let payload;
  try {
    payload = JSON.parse(analysisKeyVariableImportJsonEl.value || '');
  } catch (_error) {
    throw new Error('JSON must be valid.');
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('Import payload must be a JSON object.');
  const keyVariables = payload.key_variables;
  if (!Array.isArray(keyVariables)) throw new Error('key_variables must be an array.');
  if (!keyVariables.length) throw new Error('key_variables must contain at least 1 item.');

  const normalized = keyVariables.map((item, index) => {
    const rowNumber = index + 1;
    if (!item || typeof item !== 'object' || Array.isArray(item)) throw new Error(`Row ${rowNumber}: key variable must be an object.`);
    const variable = typeof item.variable === 'string' ? item.variable.trim() : '';
    if (!variable) throw new Error(`Row ${rowNumber}: variable must be non-empty text.`);
    if (!['Bullish', 'Bearish'].includes(item.type)) throw new Error(`Row ${rowNumber}: type must be Bullish or Bearish.`);
    const driverCategory = item.driver_category == null || item.driver_category === '' ? 'Core Driver' : item.driver_category;
    if (!['Core Driver', 'Potential Driver'].includes(driverCategory)) throw new Error(`Row ${rowNumber}: driver_category must be Core Driver or Potential Driver.`);
    const confidence = Number(item.confidence);
    const importance = Number(item.importance);
    if (!Number.isInteger(confidence) || confidence < 0 || confidence > 10) throw new Error(`Row ${rowNumber}: confidence must be an integer from 0 to 10.`);
    if (!Number.isInteger(importance) || importance < 0 || importance > 10) throw new Error(`Row ${rowNumber}: importance must be an integer from 0 to 10.`);
    return {
      variable,
      type: item.type,
      driver_category: driverCategory,
      confidence,
      importance,
    };
  });

  return {
    symbol: typeof payload.symbol === 'string' ? payload.symbol.trim() : '',
    key_variables: normalized,
  };
}

async function importKeyVariablesFromJson() {
  let importPayload;
  try {
    importPayload = parseKeyVariableImportPayload();
  } catch (error) {
    analysisKeyVariableImportStatusEl.textContent = `Error: ${error.message}`;
    analysisKeyVariableImportStatusEl.className = 'status error';
    return;
  }

  const currentSymbol = analysisDetailState?.symbol || '';
  if (importPayload.symbol && normalizeSymbolForJoin(importPayload.symbol) !== normalizeSymbolForJoin(currentSymbol)) {
    const continueMismatch = window.confirm(`Imported symbol ${importPayload.symbol} does not match current symbol ${currentSymbol}. Continue?`);
    if (!continueMismatch) return;
  }
  const shouldReplace = window.confirm('This will replace the current key variables for this analysis version. Continue?');
  if (!shouldReplace) return;

  const versionId = analysisDetailState?.version?.id;
  if (!versionId) return;
  analysisKeyVariableImportStatusEl.textContent = 'Importing key variables…';
  analysisKeyVariableImportStatusEl.className = 'status';
  try {
    const response = await fetch(`/api/analysis/${encodeURIComponent(currentSymbol)}/key-variables/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version_id: versionId, ...importPayload }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to import key variables'));
    analysisDetailState = payload.analysis;
    isEditingVariables = false;
    editableAnalysisVariables = null;
    activeAnalysisVariableCategory = 'Core Driver';
    closeKeyVariableImportModal();
    renderAnalysisDetail();
    loadAnalysis();
    analysisDetailStatus.textContent = 'Key variables imported and saved. Re-run scenarios when ready.';
    analysisDetailStatus.className = 'status';
  } catch (error) {
    analysisKeyVariableImportStatusEl.textContent = `Error: ${error.message}`;
    analysisKeyVariableImportStatusEl.className = 'status error';
  }
}

async function saveEditedVariables() {
  const variables = collectEditedVariables();
  const symbol = analysisDetailState.symbol;
  const versionId = analysisDetailState.version.id;
  analysisDetailStatus.textContent = 'Saving key variable edits…';

  try {
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}/key-variables`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version_id: versionId, key_variables: variables }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to save key variables'));
    analysisDetailState = payload.analysis;
    isEditingVariables = false;
    editableAnalysisVariables = null;
    isEditingBusinessModel = false;
    isEditingBusinessSummary = false;
    renderAnalysisDetail();
    analysisDetailStatus.textContent = 'Key variable edits saved.';
  } catch (error) {
    analysisDetailStatus.textContent = `Error: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

async function rerunScenarios() {
  const symbol = analysisDetailState.symbol;
  const versionId = analysisDetailState.version.id;
  analysisDetailStatus.textContent = 'Re-running scenarios…';

  try {
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}/rerun-scenarios`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version_id: versionId }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to re-run scenarios'));
    analysisDetailState = payload.analysis;
    isEditingVariables = false;
    isEditingBusinessModel = false;
    renderAnalysisDetail();
    loadAnalysis();
    analysisDetailStatus.textContent = 'Scenarios re-run and new version created.';
  } catch (error) {
    analysisDetailStatus.textContent = `Error: ${error.message}`;
    analysisDetailStatus.className = 'status error';
  }
}

async function loadPositions(options = {}) {
  positionsStatusEl.textContent = options.refresh ? 'Refreshing positions from TWS…' : 'Loading saved positions…';
  positionsStatusEl.className = 'status';
  positionsTable.classList.add('hidden');
  if (options.refresh) refreshBtn.disabled = true;

  try {
    let positionsPayload = null;
    let analysisPayload = null;
    let analysisResponseOk = false;
    const maxAttempts = options.refresh ? 2 : 1;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const [positionsResponse, analysisResponse] = await Promise.all([
        fetch(options.refresh ? '/api/positions?refresh=1' : '/api/positions'),
        fetch('/api/analysis'),
      ]);
      positionsPayload = await positionsResponse.json();
      analysisPayload = await analysisResponse.json();
      analysisResponseOk = analysisResponse.ok;
      if (!positionsResponse.ok) throw new Error(extractErrorMessage(positionsPayload, 'Request failed'));
      if (options.refresh && attempt === 0 && shouldRetryTwsPositionsRefresh(positionsPayload)) {
        positionsStatusEl.textContent = 'Connecting to TWS… retrying refresh once.';
        await delay(750);
        positionsStatusEl.textContent = 'Refreshing positions from TWS…';
        continue;
      }
      break;
    }

    console.debug('[positions] raw /api/positions response sample:', {
      count: (positionsPayload.positions || []).length,
      first: (positionsPayload.positions || [])[0] || null,
    });
    console.debug('[positions] raw /api/analysis response sample:', {
      ok: analysisResponseOk,
      topLevelKeys: analysisPayload && typeof analysisPayload === 'object' ? Object.keys(analysisPayload) : [],
      count: Array.isArray(analysisPayload?.analysis) ? analysisPayload.analysis.length : 0,
      first: Array.isArray(analysisPayload?.analysis) ? (analysisPayload.analysis[0] || null) : null,
    });

    latestPositionsPortfolioSummary = positionsPayload.portfolio_summary || null;
    renderPositionsPortfolioSummary(latestPositionsPortfolioSummary);
    latestPositions = mergePositionsWithAnalysis(
      positionsPayload.positions || [],
      analysisResponseOk ? analysisPayload : [],
    );

    console.debug('[positions] merged rows sample:', {
      count: latestPositions.length,
      first: latestPositions[0] || null,
      withRating: latestPositions.filter((row) => !!row.rating).length,
      withUpside: latestPositions.filter((row) => typeof row.upside === 'number').length,
      withConfidence: latestPositions.filter((row) => typeof row.confidence_diff === 'number').length,
    });

    saveCachedPositions(latestPositions);

    if (!latestPositions.length) {
      positionsTableBody.innerHTML = '';
      positionsStatusEl.textContent = positionsPayload.warning || 'No positions found.';
      if (positionsPayload.warning) positionsStatusEl.className = 'status error';
      return;
    }

    updateSortHeaderState();
    renderPositions();
    const source = positionsPayload.data_source ? ` source=${positionsPayload.data_source}` : '';
    positionsStatusEl.textContent = positionsPayload.warning
      ? `${positionsPayload.warning} Loaded ${latestPositions.length} position(s).${source}`
      : `Loaded ${latestPositions.length} position(s).${source}`;
    positionsStatusEl.className = positionsPayload.warning ? 'status error' : 'status';
    positionsTable.classList.remove('hidden');
  } catch (error) {
    if (latestPositions.length) {
      console.debug('[positions] using cached/fallback positions path', {
        cachedCount: latestPositions.length,
        withRating: latestPositions.filter((row) => !!row.rating).length,
      });
      updateSortHeaderState();
      renderPositionsPortfolioSummary(latestPositionsPortfolioSummary);
      renderPositions();
      positionsTable.classList.remove('hidden');
      positionsStatusEl.textContent = `Warning: ${error.message} Showing latest loaded positions.`;
      positionsStatusEl.className = 'status error';
      return;
    }

    positionsStatusEl.textContent = `Error: ${error.message}`;
    positionsStatusEl.className = 'status error';
  } finally {
    if (options.refresh) refreshBtn.disabled = false;
  }
}


async function loadAnalysis() {
  analysisStatusEl.textContent = 'Loading analysis…'; analysisStatusEl.className = 'status'; analysisTable.classList.add('hidden');
  try {
    const [analysisResponse, positionsResponse] = await Promise.all([
      fetch('/api/analysis'),
      fetch('/api/positions'),
    ]);
    const analysisPayload = await analysisResponse.json();
    const positionsPayload = await positionsResponse.json();
    if (!analysisResponse.ok) throw new Error(extractErrorMessage(analysisPayload, 'Request failed'));
    latestAnalysis = enrichAnalysisWithPortfolioStatus(analysisPayload.analysis || []);
    if (positionsResponse.ok) {
      latestPositions = mergePositionsWithAnalysis(positionsPayload.positions || [], latestAnalysis);
      saveCachedPositions(latestPositions);
      console.debug('[analysis] refreshed cached positions with analysis enrichment', {
        positionsCount: latestPositions.length,
        withRating: latestPositions.filter((row) => !!row.rating).length,
      });
    }

    analysisTableBody.innerHTML = '';
    selectedAnalysisSymbols = new Set([...selectedAnalysisSymbols].filter((symbol) => latestAnalysis.some((item) => item.symbol === symbol)));
    if (!latestAnalysis.length) { analysisStatusEl.textContent = 'Analysis is empty.'; syncSelectAllCheckbox(); return; }
    updateAnalysisSortHeaderState();
    renderAnalysisList();
    analysisStatusEl.textContent = `Loaded ${latestAnalysis.length} analysis symbol(s).`;
    analysisTable.classList.remove('hidden');
  } catch (error) { analysisStatusEl.textContent = `Error: ${error.message}`; analysisStatusEl.className = 'status error'; }
}

async function rerunSelectedSymbolsScenarios() {
  const symbols = [...selectedAnalysisSymbols];
  if (!symbols.length) {
    analysisStatusEl.textContent = 'Select at least one symbol first.';
    analysisStatusEl.className = 'status error';
    return;
  }

  analysisStatusEl.textContent = `Preparing scenario rerun for ${symbols.length} symbol(s)…`;
  analysisStatusEl.className = 'status';
  try {
    const scenarioPassCount = await getScenarioPassCountForStatus();
    let okCount = 0;
    let failCount = 0;
    for (const symbol of symbols) {
      analysisStatusEl.textContent = buildScenarioStatusMessage(symbol, scenarioPassCount);
      try {
        const detailResponse = await fetch(`/api/analysis/${encodeURIComponent(symbol)}`);
        const detailPayload = await detailResponse.json();
        if (!detailResponse.ok) throw new Error(extractErrorMessage(detailPayload, 'Unable to load symbol detail'));
        const versionId = detailPayload.analysis?.selected_version_id;
        if (!versionId) throw new Error('Missing version id');

        const rerunResponse = await fetch(`/api/analysis/${encodeURIComponent(symbol)}/rerun-scenarios`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ version_id: versionId }),
        });
        const rerunPayload = await rerunResponse.json();
        if (!rerunResponse.ok) throw new Error(extractErrorMessage(rerunPayload, 'Unable to re-run scenarios'));
        okCount += 1;
      } catch (error) {
        console.error(`Failed rerun for ${symbol}:`, error);
        failCount += 1;
      }
    }

    await loadAnalysis();
    analysisStatusEl.textContent = failCount ? `Re-ran ${okCount} symbol(s), ${failCount} failed.` : `Re-ran scenarios for ${okCount} symbol(s).`;
    analysisStatusEl.className = failCount ? 'status error' : 'status';
  } catch (error) {
    analysisStatusEl.textContent = `Error: ${error.message}`;
    analysisStatusEl.className = 'status error';
  }
}

async function checkRecentEventsForSelected() {
  const symbols = [...selectedAnalysisSymbols];
  if (!symbols.length) {
    analysisStatusEl.textContent = 'Select at least one symbol first.';
    analysisStatusEl.className = 'status error';
    return;
  }

  analysisStatusEl.textContent = `Checking recent events for ${symbols.length} symbol(s)…`;
  analysisStatusEl.className = 'status';
  try {
    const response = await fetch('/api/alerts/check-recent-events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols }),
    });
    const payload = await response.json();
    if (!response.ok && response.status !== 207) throw new Error(extractErrorMessage(payload, 'Unable to check recent events'));
    analysisStatusEl.textContent = `Checked ${payload.symbols_checked || 0} symbols. Created ${payload.alerts_created || 0} alerts. ${payload.no_material_impact_count || 0} symbol(s) had no material thesis impact.`;
    analysisStatusEl.className = payload.errors_count ? 'status error' : 'status';
  } catch (error) {
    analysisStatusEl.textContent = `Error: ${error.message}`;
    analysisStatusEl.className = 'status error';
  }
}

async function addAnalysisSymbol() {
  const symbol = analysisSymbolInput.value.trim().toUpperCase(); if (!symbol) return;
  analysisStatusEl.className = 'status';
  const scenarioPassCount = await getScenarioPassCountForStatus();
  analysisStatusEl.textContent = buildScenarioStatusMessage(symbol, scenarioPassCount);
  try { const response = await fetch('/api/analysis', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol }) });
    const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to add analysis'));
    analysisSymbolInput.value = ''; await loadAnalysis();
    analysisStatusEl.textContent = `Analysis completed for ${symbol}.`;
  } catch (error) { analysisStatusEl.textContent = `Error: ${error.message}`; analysisStatusEl.className = 'status error'; }
}

async function importAnalysisFromPositions() {
  analysisStatusEl.textContent = 'Importing from positions…'; analysisStatusEl.className = 'status';
  try { const response = await fetch('/api/analysis/import-from-positions', { method: 'POST' }); const payload = await response.json();
    if (!response.ok && response.status !== 207) throw new Error(extractErrorMessage(payload, 'Unable to import analysis'));
    await loadAnalysis();
    const importedCount = payload.importedSymbols?.length || 0;
    const skippedCount = payload.skippedSymbols?.length || 0;
    const failedCount = payload.failures?.length || 0;
    if (failedCount) {
      analysisStatusEl.textContent = `Imported ${importedCount} symbol(s), skipped ${skippedCount} existing, ${failedCount} failed.`;
      analysisStatusEl.className = 'status error';
    } else {
      analysisStatusEl.textContent = `Imported ${importedCount} symbol(s), skipped ${skippedCount} existing.`;
      analysisStatusEl.className = 'status';
    }
  } catch (error) { analysisStatusEl.textContent = `Error: ${error.message}`; analysisStatusEl.className = 'status error'; }
}

async function refreshAnalysisPrices() {
  analysisStatusEl.textContent = 'Updating current prices…'; analysisStatusEl.className = 'status';
  analysisRefreshPricesBtn.disabled = true;
  try {
    let payload = null;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const response = await fetch('/api/analysis/refresh-prices', { method: 'POST' });
      payload = await response.json();
      if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to refresh analysis prices'));
      if (attempt === 0 && shouldRetryTwsAnalysisPriceRefresh(payload)) {
        analysisStatusEl.textContent = 'Connecting to TWS… retrying price refresh once.';
        await delay(750);
        analysisStatusEl.textContent = 'Updating current prices…';
        continue;
      }
      break;
    }
    latestAnalysis = enrichAnalysisWithPortfolioStatus(payload.analysis || []);
    updateAnalysisSortHeaderState();
    renderAnalysisList();
    analysisTable.classList.toggle('hidden', latestAnalysis.length === 0);
    const skippedSymbolsText = formatSkippedPriceSymbols(payload.skipped_symbols);
    const fallbackSymbolsText = formatSkippedPriceSymbols(payload.fallback_symbols);
    const keptPreviousSymbolsText = formatSkippedPriceSymbols(payload.kept_previous_symbols);
    logFallbackPriceDetails(payload.fallback_symbols, payload.kept_previous_symbols);
    if (payload.skipped) logSkippedPriceDetails(payload.skipped_symbols);
    const statusParts = [`Updated ${payload.updated || 0} symbol(s)`];
    if (payload.fallback_symbols?.length) statusParts.push(`fallback used for ${payload.fallback_symbols.length}: ${fallbackSymbolsText}`);
    if (payload.kept_previous) statusParts.push(`kept previous price for ${payload.kept_previous}: ${keptPreviousSymbolsText}`);
    if (payload.skipped) statusParts.push(`skipped ${payload.skipped}: ${skippedSymbolsText}`);
    analysisStatusEl.textContent = `${statusParts.join(', ')}.`;
  } catch (error) {
    analysisStatusEl.textContent = `Error: ${error.message}`;
    analysisStatusEl.className = 'status error';
  } finally {
    analysisRefreshPricesBtn.disabled = false;
  }
}


async function updateAnalysisMomentum() {
  const selectedSymbols = [...selectedAnalysisSymbols];
  const symbols = selectedSymbols.length ? selectedSymbols : getVisibleAnalysisSymbols();
  if (!symbols.length) {
    analysisStatusEl.textContent = 'No analysis symbols to update momentum for.';
    analysisStatusEl.className = 'status error';
    return;
  }
  analysisStatusEl.textContent = `Updating momentum for ${symbols.length} symbol(s)…`;
  analysisStatusEl.className = 'status';
  analysisUpdateMomentumBtn.disabled = true;
  try {
    const response = await fetch('/api/analysis/momentum/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols }),
    });
    const payload = await response.json();
    if (!response.ok && response.status !== 207) throw new Error(extractErrorMessage(payload, 'Unable to update momentum'));
    await loadAnalysis();
    const updatedCount = payload.updated?.length || 0;
    const failedCount = payload.errors?.length || 0;
    if (failedCount) console.warn('Momentum update failures:', payload.errors);
    analysisStatusEl.textContent = failedCount
      ? `Momentum updated for ${updatedCount} symbol(s); ${failedCount} failed.`
      : `Momentum updated for ${updatedCount} symbol(s).`;
    analysisStatusEl.className = failedCount ? 'status error' : 'status';
  } catch (error) {
    analysisStatusEl.textContent = `Error: ${error.message}`;
    analysisStatusEl.className = 'status error';
  } finally {
    analysisUpdateMomentumBtn.disabled = false;
  }
}


async function deleteAnalysis(symbol) {
  analysisStatusEl.textContent = `Deleting ${symbol}…`; analysisStatusEl.className = 'status';
  try { const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}`, { method: 'DELETE' }); const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to delete')); await loadAnalysis();
  } catch (error) { analysisStatusEl.textContent = `Error: ${error.message}`; analysisStatusEl.className = 'status error'; }
}

function showAlertsListView() {
  currentAlertDetailId = null;
  currentAlertDetailSymbol = null;
  currentAlertNavigationIds = [];
  alertDetailAnalysisState = null;
  alertDetailIsEditingVariables = false;
  alertsListView.classList.remove('hidden');
  alertDetailView.classList.add('hidden');
}

function getFilteredAlerts() {
  if (alertsStatusFilter === 'All') return latestAlerts;
  return latestAlerts.filter((alert) => (alert.status || 'New') === alertsStatusFilter);
}

function getCurrentAlertIndexWithinFiltered() {
  if (!currentAlertDetailId) return -1;
  if (currentAlertNavigationIds.length) return currentAlertNavigationIds.indexOf(String(currentAlertDetailId));
  const filtered = getFilteredAlerts();
  return filtered.findIndex((item) => String(item.id) === String(currentAlertDetailId));
}

async function openNextAlertDetail() {
  const navigationIds = currentAlertNavigationIds.length
    ? currentAlertNavigationIds
    : getFilteredAlerts().map((item) => String(item.id));
  const index = getCurrentAlertIndexWithinFiltered();
  const nextId = index >= 0 ? navigationIds[index + 1] : null;
  const next = nextId ? latestAlerts.find((item) => String(item.id) === String(nextId)) : null;
  if (!next) {
    alertDetailStatusEl.textContent = 'No next alert in current filter.';
    alertDetailStatusEl.className = 'status';
    return;
  }
  await openAlertDetail(next.id);
}

async function openPreviousAlertDetail() {
  const navigationIds = currentAlertNavigationIds.length
    ? currentAlertNavigationIds
    : getFilteredAlerts().map((item) => String(item.id));
  const index = getCurrentAlertIndexWithinFiltered();
  const prevId = index > 0 ? navigationIds[index - 1] : null;
  const prev = prevId ? latestAlerts.find((item) => String(item.id) === String(prevId)) : null;
  if (!prev) {
    alertDetailStatusEl.textContent = 'No previous alert in current filter.';
    alertDetailStatusEl.className = 'status';
    return;
  }
  await openAlertDetail(prev.id);
}

async function refreshAlertsData() {
  const response = await fetch('/api/alerts');
  const payload = await response.json();
  if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load alerts'));
  latestAlerts = payload.alerts || [];
  return payload;
}

function renderAlertSources(sources) {
  alertDetailSourcesEl.innerHTML = '';
  const items = Array.isArray(sources) ? sources : [];
  if (!items.length) {
    const li = document.createElement('li');
    li.textContent = '—';
    alertDetailSourcesEl.appendChild(li);
    return;
  }
  items.forEach((source) => {
    const li = document.createElement('li');
    const label = [source.source_name, source.published_at].filter(Boolean).join(' · ');
    if (source.url) {
      const link = document.createElement('a');
      link.href = source.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = source.title || source.url;
      li.appendChild(link);
      if (label) li.append(` (${label})`);
    } else {
      li.textContent = [source.title || 'Source', label].filter(Boolean).join(' · ');
    }
    alertDetailSourcesEl.appendChild(li);
  });
}

function getAlertDetailEffectiveVariables() {
  if (!alertDetailAnalysisState?.version) return [];
  const saved = alertDetailAnalysisState.saved_key_variable_edits;
  if (saved && Number(saved.based_on_version_id) === Number(alertDetailAnalysisState.version.id)) {
    return saved.key_variables || [];
  }
  return alertDetailAnalysisState.version.key_variables || [];
}

function renderAlertDetailVariablesTable() {
  const hasAnalysis = Boolean(alertDetailAnalysisState?.version);
  const variables = getAlertDetailEffectiveVariables();
  alertDetailVarsBody.innerHTML = '';
  variables.forEach((variable) => {
    const row = document.createElement('tr');
    const variableType = variable.variable_type || 'Bullish';
    const driverCategory = normalizeDriverCategory(variable.driver_category);
    row.innerHTML = alertDetailIsEditingVariables
      ? `<td><input class="alert-var-text" type="text" value="${escapeHtml(variable.variable_text || '')}"></td><td><select class="alert-var-type"><option value="Bullish" ${variableType === 'Bullish' ? 'selected' : ''}>Bullish</option><option value="Bearish" ${variableType === 'Bearish' ? 'selected' : ''}>Bearish</option></select></td><td>${renderDriverCategorySelect('alert-var-driver-category', driverCategory)}</td><td><input class="alert-var-confidence" type="number" min="0" max="10" step="1" value="${Number(variable.confidence ?? 0)}"></td><td><input class="alert-var-importance" type="number" min="0" max="10" step="1" value="${Number(variable.importance ?? 0)}"></td><td><button class="alert-var-delete-btn">Delete</button></td>`
      : `<td>${escapeHtml(variable.variable_text || '')}</td><td>${escapeHtml(variableType)}</td><td>${escapeHtml(driverCategory)}</td><td>${formatNumber(variable.confidence, 2)}</td><td>${formatNumber(variable.importance, 2)}</td><td>—</td>`;
    alertDetailVarsBody.appendChild(row);
  });

  if (alertDetailIsEditingVariables) {
    alertDetailVarsBody.querySelectorAll('.alert-var-delete-btn').forEach((button) => {
      button.addEventListener('click', () => {
        button.closest('tr')?.remove();
      });
    });
  }

  alertDetailEditVarsBtn.classList.toggle('hidden', alertDetailIsEditingVariables || !hasAnalysis);
  alertDetailAddVarBtn.classList.toggle('hidden', !alertDetailIsEditingVariables || !hasAnalysis);
  alertDetailSaveVarsBtn.classList.toggle('hidden', !alertDetailIsEditingVariables || !hasAnalysis);
  alertDetailCancelVarsBtn.classList.toggle('hidden', !alertDetailIsEditingVariables || !hasAnalysis);
  alertDetailRerunBtn.disabled = !hasAnalysis;
  alertDetailOpenAnalysisBtn.disabled = !currentAlertDetailSymbol;
}

function collectEditedAlertDetailVariables() {
  return [...alertDetailVarsBody.querySelectorAll('tr')].map((row) => ({
    variable_text: row.querySelector('.alert-var-text')?.value?.trim() || '',
    variable_type: row.querySelector('.alert-var-type')?.value || 'Bullish',
    driver_category: normalizeDriverCategory(row.querySelector('.alert-var-driver-category')?.value),
    confidence: Number(row.querySelector('.alert-var-confidence')?.value),
    importance: Number(row.querySelector('.alert-var-importance')?.value),
  }));
}

async function loadAlertDetailAnalysis(symbol) {
  if (!symbol) {
    alertDetailKeyvarsStatusEl.textContent = 'Error: Missing symbol for this alert.';
    alertDetailKeyvarsStatusEl.className = 'status error';
    return;
  }
  alertDetailKeyvarsStatusEl.textContent = `Loading key variables for ${symbol}…`;
  alertDetailKeyvarsStatusEl.className = 'status';
  alertDetailAnalysisState = null;
  alertDetailIsEditingVariables = false;
  renderAlertDetailVariablesTable();
  try {
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load analysis detail'));
    alertDetailAnalysisState = payload.analysis;
    renderAlertDetailVariablesTable();
    alertDetailKeyvarsStatusEl.textContent = `Loaded ${getAlertDetailEffectiveVariables().length} key variable(s) from version ${alertDetailAnalysisState.version.version_number}.`;
  } catch (error) {
    alertDetailKeyvarsStatusEl.textContent = `Error: ${error.message}`;
    alertDetailKeyvarsStatusEl.className = 'status error';
  }
}

async function saveAlertDetailVariables() {
  if (!alertDetailAnalysisState?.version) return;
  const symbol = alertDetailAnalysisState.symbol;
  const versionId = alertDetailAnalysisState.version.id;
  const keyVariables = collectEditedAlertDetailVariables();
  alertDetailKeyvarsStatusEl.textContent = 'Saving key variable edits…';
  alertDetailKeyvarsStatusEl.className = 'status';
  try {
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}/key-variables`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version_id: versionId, key_variables: keyVariables }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to save key variables'));
    alertDetailAnalysisState = payload.analysis;
    alertDetailIsEditingVariables = false;
    renderAlertDetailVariablesTable();
    alertDetailKeyvarsStatusEl.textContent = 'Key variable edits saved.';
  } catch (error) {
    alertDetailKeyvarsStatusEl.textContent = `Error: ${error.message}`;
    alertDetailKeyvarsStatusEl.className = 'status error';
  }
}

async function rerunAlertDetailScenarios() {
  if (!alertDetailAnalysisState?.version) return;
  const symbol = alertDetailAnalysisState.symbol;
  const versionId = alertDetailAnalysisState.version.id;
  alertDetailKeyvarsStatusEl.textContent = 'Re-running scenarios…';
  alertDetailKeyvarsStatusEl.className = 'status';
  try {
    const response = await fetch(`/api/analysis/${encodeURIComponent(symbol)}/rerun-scenarios`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version_id: versionId }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to re-run scenarios'));
    alertDetailAnalysisState = payload.analysis;
    alertDetailIsEditingVariables = false;
    renderAlertDetailVariablesTable();
    alertDetailKeyvarsStatusEl.textContent = `Scenarios re-run. New version ${alertDetailAnalysisState.version.version_number} created.`;
    loadAnalysis();
  } catch (error) {
    alertDetailKeyvarsStatusEl.textContent = `Error: ${error.message}`;
    alertDetailKeyvarsStatusEl.className = 'status error';
  }
}

async function backToAlertsFromDetail() {
  await loadAlerts();
}

function renderAlertsList() {
  alertsTableBody.innerHTML = '';
  getFilteredAlerts().forEach((alert) => {
    const row = document.createElement('tr');
    const affected = (alert.affected_variables || []).join(', ') || '—';
    row.innerHTML = `<td><button class="symbol-link" data-alert-id="${alert.id}">${escapeHtml(alert.symbol || '')}</button></td><td>${escapeHtml(alert.alert_type || '—')}</td><td>${alert.event_date ? formatDate(alert.event_date) : formatDateTime(alert.created_at)}</td><td>${escapeHtml(alert.status || 'New')}</td><td>${escapeHtml(affected)}</td><td><button class="alert-review-btn" data-id="${alert.id}">Mark Reviewed</button> <button class="alert-dismiss-btn" data-id="${alert.id}">Dismiss</button></td>`;
    alertsTableBody.appendChild(row);
  });
  alertsTableBody.querySelectorAll('.alert-review-btn').forEach((btn) => btn.addEventListener('click', async () => updateAlertStatus(btn.dataset.id, 'Reviewed')));
  alertsTableBody.querySelectorAll('.alert-dismiss-btn').forEach((btn) => btn.addEventListener('click', async () => updateAlertStatus(btn.dataset.id, 'Dismissed')));
  alertsTableBody.querySelectorAll('.symbol-link').forEach((btn) => btn.addEventListener('click', async () => openAlertDetail(btn.dataset.alertId)));
}

async function openAlertDetail(alertId) {
  currentAlertDetailId = alertId;
  currentAlertNavigationIds = getFilteredAlerts().map((item) => String(item.id));
  alertsListView.classList.add('hidden');
  alertDetailView.classList.remove('hidden');
  alertDetailStatusEl.textContent = 'Loading alert detail…';
  alertDetailStatusEl.className = 'status';
  alertDetailPanelsEl.classList.add('hidden');
  try {
    const response = await fetch(`/api/alerts/${encodeURIComponent(alertId)}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load alert detail'));
    const alert = payload.alert || {};
    currentAlertDetailSymbol = alert.symbol || null;
    alertDetailTitleEl.textContent = `Alert Detail · ${alert.symbol || ''}`;
    alertDetailTypeEl.textContent = alert.alert_type || '—';
    alertDetailAffectedEl.textContent = (alert.affected_variables || []).join(', ') || '—';
    alertDetailEventEl.textContent = alert.event_summary || '—';
    alertDetailDateEl.textContent = alert.event_date ? formatDate(alert.event_date) : formatDateTime(alert.created_at);
    alertDetailSuggestedEl.textContent = alert.suggested_action || '—';
    alertDetailReviewBtn.disabled = false;
    alertDetailDismissBtn.disabled = false;
    const currentIndex = getCurrentAlertIndexWithinFiltered();
    alertDetailPrevBtn.disabled = currentIndex <= 0;
    alertDetailNextBtn.disabled = currentIndex < 0 || currentIndex >= (currentAlertNavigationIds.length - 1);
    renderAlertSources(alert.event_sources || []);
    alertDetailPanelsEl.classList.remove('hidden');
    alertDetailStatusEl.textContent = `Status: ${alert.status || 'New'}`;
    loadAlertDetailAnalysis(alert.symbol || '').catch((error) => {
      alertDetailKeyvarsStatusEl.textContent = `Error: ${error.message}`;
      alertDetailKeyvarsStatusEl.className = 'status error';
    });
  } catch (error) {
    currentAlertDetailSymbol = null;
    alertDetailStatusEl.textContent = `Error: ${error.message}`;
    alertDetailStatusEl.className = 'status error';
    alertDetailReviewBtn.disabled = true;
    alertDetailDismissBtn.disabled = true;
    alertDetailPrevBtn.disabled = true;
    alertDetailNextBtn.disabled = true;
    alertDetailOpenAnalysisBtn.disabled = true;
  }
}

async function loadAlerts() {
  showAlertsListView();
  alertsStatusEl.textContent = 'Loading alerts…';
  alertsStatusEl.className = 'status';
  alertsTable.classList.add('hidden');
  try {
    await refreshAlertsData();
    if (!latestAlerts.length) {
      alertsStatusEl.textContent = 'No alerts found.';
      return;
    }
    renderAlertsList();
    const visibleCount = getFilteredAlerts().length;
    alertsTable.classList.remove('hidden');
    alertsStatusEl.textContent = `Showing ${visibleCount} of ${latestAlerts.length} alert(s).`;
  } catch (error) {
    alertsStatusEl.textContent = `Error: ${error.message}`;
    alertsStatusEl.className = 'status error';
  }
}

async function updateAlertStatus(alertId, status, options = {}) {
  const stayOnDetail = options.stayOnDetail === true;
  const advanceAfterUpdate = options.advanceAfterUpdate === true;
  const filteredBefore = currentAlertNavigationIds.length
    ? currentAlertNavigationIds.map((id) => ({ id }))
    : getFilteredAlerts();
  const currentIndexBefore = getCurrentAlertIndexWithinFiltered();
  const nextAlertIdBefore = currentIndexBefore >= 0 && currentIndexBefore < (filteredBefore.length - 1)
    ? filteredBefore[currentIndexBefore + 1]?.id
    : null;
  try {
    const response = await fetch(`/api/alerts/${encodeURIComponent(alertId)}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to update alert status'));

    await refreshAlertsData();

    if (stayOnDetail) {
      if (advanceAfterUpdate) {
        const next = nextAlertIdBefore && getFilteredAlerts().find((item) => String(item.id) === String(nextAlertIdBefore));
        if (next) {
          await openAlertDetail(next.id);
        } else {
          await backToAlertsFromDetail();
        }
      } else {
        await openAlertDetail(alertId);
      }
      return;
    }

    await loadAlerts();
  } catch (error) {
    if (stayOnDetail) {
      alertDetailStatusEl.textContent = `Error: ${error.message}`;
      alertDetailStatusEl.className = 'status error';
      return;
    }
    alertsStatusEl.textContent = `Error: ${error.message}`;
    alertsStatusEl.className = 'status error';
  }
}

function renderEarningsReviewList() {
  earningsReviewTableBody.innerHTML = '';
  earningsReviewItems.forEach((item) => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><button class="symbol-link earnings-select-btn" data-symbol="${item.symbol}">${item.symbol}</button></td>
      <td>${item.in_portfolio ? 'Yes' : 'No'}</td>
      <td>${item.rating || 'N/A'}</td>
      <td>${item.latest_quarter || 'N/A'}</td>
      <td>${item.latest_review_status || 'No review yet'}</td>
    `;
    earningsReviewTableBody.appendChild(row);
  });
  earningsReviewTableBody.querySelectorAll('.earnings-select-btn').forEach((btn) => {
    btn.addEventListener('click', () => openEarningsReviewSymbolHistory(btn.dataset.symbol));
  });
  if (earningsReviewItems.length) {
    earningsReviewStatusEl.textContent = `Showing ${earningsReviewItems.length} symbol(s).`;
    earningsReviewStatusEl.className = 'status';
  }
}

function setEarningsReviewTab(tab) {
  earningsReviewActiveTab = tab === 'calendar' ? 'calendar' : 'workflow';
  const showCalendar = earningsReviewActiveTab === 'calendar';
  earningsReviewTabWorkflowBtn.classList.toggle('active', !showCalendar);
  earningsReviewTabCalendarBtn.classList.toggle('active', showCalendar);
  earningsReviewWorkflowPanelEl.classList.toggle('hidden', showCalendar);
  earningsReviewCalendarPanelEl.classList.toggle('hidden', !showCalendar);
}

function parseCalendarDate(value) {
  if (!value || typeof value !== 'string') return null;
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null;
  const parsed = new Date(year, month - 1, day);
  if (Number.isNaN(parsed.getTime())) return null;
  if (parsed.getFullYear() !== year || parsed.getMonth() !== (month - 1) || parsed.getDate() !== day) return null;
  return parsed;
}

function formatCalendarDateInputValue(isoDateValue) {
  if (!isoDateValue) return '';
  const parsed = parseCalendarDate(isoDateValue);
  if (!parsed) return '';
  const day = String(parsed.getDate()).padStart(2, '0');
  const month = String(parsed.getMonth() + 1).padStart(2, '0');
  const year = parsed.getFullYear();
  return `${day}.${month}.${year}`;
}

function parseCalendarDisplayDateToIso(displayDateValue) {
  const raw = String(displayDateValue || '').trim();
  if (!raw) return { ok: true, isoDate: null };
  const match = raw.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (!match) {
    return { ok: false, error: 'Release date must use DD.MM.YYYY format.' };
  }
  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = Number(match[3]);
  const parsed = new Date(year, month - 1, day);
  const isValid = !Number.isNaN(parsed.getTime())
    && parsed.getFullYear() === year
    && parsed.getMonth() === (month - 1)
    && parsed.getDate() === day;
  if (!isValid) {
    return { ok: false, error: 'Release date is invalid. Please use a real DD.MM.YYYY date.' };
  }
  const isoDate = `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  return { ok: true, isoDate };
}

function releaseDateMatchesEarningsCalendarDateFilters(releaseDateValue, today, selectedDateFilters) {
  return window.EarningsCalendarDateFilters.releaseDateMatchesEarningsCalendarDateFilters(
    releaseDateValue,
    today,
    selectedDateFilters,
  );
}

function getFilteredAndSortedEarningsCalendarItems() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const selectedDateFilters = getSelectedEarningsCalendarDateFilters();
  const selectedFiscalYears = getSelectedEarningsCalendarFiscalYears();
  const selectedFiscalQuarters = getSelectedEarningsCalendarFiscalQuarters();
  const availableYearCount = getAvailableEarningsCalendarFiscalYears().length;
  const filtered = earningsCalendarItems.filter((item) => window.EarningsCalendarDateFilters.earningsCalendarItemMatchesFilters(item, {
    today,
    selectedDateFilters,
    portfolioFilter: earningsCalendarPortfolioFilter,
    selectedFiscalYears,
    availableYearCount,
    selectedFiscalQuarters,
    quarterOptionCount: EARNINGS_CALENDAR_QUARTER_FILTER_OPTIONS.length,
  }));
  return filtered.sort((left, right) => window.EarningsCalendarDateFilters.compareEarningsCalendarItems(
    left,
    right,
    earningsCalendarReleaseDateSortDirection,
  ));
}

function getEarningsCalendarQuarterOptions(selectedQuarter) {
  return ['Q1', 'Q2', 'Q3', 'Q4']
    .map((value) => `<option value="${value}" ${value === selectedQuarter ? 'selected' : ''}>${value}</option>`)
    .join('');
}

function getEarningsCalendarTimingOptions(selectedTiming) {
  return ['', 'Before Open', 'After Close']
    .map((value) => `<option value="${value}" ${value === (selectedTiming || '') ? 'selected' : ''}>${value || 'Not set'}</option>`)
    .join('');
}

function parseEarningsCalendarFiscalYear(value) {
  const raw = String(value || '').trim();
  if (!raw) return { ok: false, error: 'Fiscal year is required.' };
  const year = Number(raw);
  if (!Number.isInteger(year) || year < 1900 || year > 2200) {
    return { ok: false, error: 'Fiscal year must be an integer between 1900 and 2200.' };
  }
  return { ok: true, year };
}

function renderEarningsCalendarTable() {
  earningsCalendarTableBody.innerHTML = '';
  syncEarningsCalendarFiscalYearFilterOptions();
  setSelectedEarningsCalendarFiscalQuarters(earningsCalendarFiscalQuarterFilters);
  const items = getFilteredAndSortedEarningsCalendarItems();
  earningsCalendarReleaseDateHeaderEl.dataset.sortDirection = earningsCalendarReleaseDateSortDirection;
  items.forEach((item) => {
    const row = document.createElement('tr');
    const entryId = String(item.id || '');
    const symbol = String(item.symbol || '');
    const upsideClass = typeof item.upside === 'number' ? valueClass(item.upside) : '';
    const symbolCell = item.has_analysis
      ? `<button class="symbol-link earnings-calendar-symbol-link" data-symbol="${escapeHtml(symbol)}">${escapeHtml(symbol)}</button>`
      : escapeHtml(symbol);
    const quarterOptions = getEarningsCalendarQuarterOptions(item.fiscal_quarter || 'Q1');
    const timingOptions = getEarningsCalendarTimingOptions(item.release_timing || '');
    row.innerHTML = `
      <td>${symbolCell}</td>
      <td>${escapeHtml(item.company_name || 'N/A')}</td>
      <td class="earnings-calendar-cell"><input type="number" class="earnings-calendar-fiscal-year earnings-calendar-date-input" data-entry-id="${escapeHtml(entryId)}" value="${escapeHtml(String(item.fiscal_year || ''))}" min="1900" max="2200" step="1" /></td>
      <td class="earnings-calendar-cell"><select class="earnings-calendar-fiscal-quarter earnings-calendar-select" data-entry-id="${escapeHtml(entryId)}">${quarterOptions}</select></td>
      <td class="earnings-calendar-cell"><input type="text" class="earnings-calendar-date earnings-calendar-date-input earnings-calendar-date-text" data-entry-id="${escapeHtml(entryId)}" value="${escapeHtml(formatCalendarDateInputValue(item.release_date))}" placeholder="DD.MM.YYYY" inputmode="numeric" /></td>
      <td class="earnings-calendar-cell"><select class="earnings-calendar-timing earnings-calendar-select" data-entry-id="${escapeHtml(entryId)}">${timingOptions}</select></td>
      <td><span class="badge ${item.in_portfolio ? 'badge-portfolio-in' : 'badge-portfolio-out'}">${item.in_portfolio ? 'In Portfolio' : 'Not in Portfolio'}</span></td>
      <td class="${upsideClass}">${formatPercent(item.upside)}</td>
      <td>${formatConfidenceDiffDisplay(item.confidence_diff, item.bullish_confidence, item.bearish_confidence)}</td>
      <td>${escapeHtml(item.rating || 'N/A')}</td>
      <td><button class="earnings-calendar-save-btn" data-entry-id="${escapeHtml(entryId)}" data-symbol="${escapeHtml(symbol)}">Save</button></td>
      <td><button class="remove-btn earnings-calendar-remove-btn" data-entry-id="${escapeHtml(entryId)}" data-symbol="${escapeHtml(symbol)}">Remove</button></td>
    `;
    earningsCalendarTableBody.appendChild(row);
  });
  earningsCalendarStatusEl.textContent = `Showing ${items.length} of ${earningsCalendarItems.length} calendar entr${earningsCalendarItems.length === 1 ? 'y' : 'ies'}.`;
  earningsCalendarStatusEl.className = 'status';
  earningsCalendarTableBody.querySelectorAll('.earnings-calendar-save-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const entryId = btn.dataset.entryId;
      const symbol = btn.dataset.symbol || 'entry';
      const row = btn.closest('tr');
      if (!row || !entryId) return;
      const fiscalYearInput = row.querySelector('.earnings-calendar-fiscal-year');
      const yearParse = parseEarningsCalendarFiscalYear(fiscalYearInput?.value || '');
      if (!yearParse.ok) {
        earningsCalendarStatusEl.textContent = `Error: ${yearParse.error}`;
        earningsCalendarStatusEl.className = 'status error';
        fiscalYearInput?.classList.add('input-error');
        return;
      }
      fiscalYearInput?.classList.remove('input-error');
      const releaseDateText = row.querySelector('.earnings-calendar-date-text')?.value || '';
      const dateParse = parseCalendarDisplayDateToIso(releaseDateText);
      if (!dateParse.ok) {
        earningsCalendarStatusEl.textContent = `Error: ${dateParse.error}`;
        earningsCalendarStatusEl.className = 'status error';
        row.querySelector('.earnings-calendar-date-text')?.classList.add('input-error');
        return;
      }
      row.querySelector('.earnings-calendar-date-text')?.classList.remove('input-error');
      const fiscalQuarter = row.querySelector('.earnings-calendar-fiscal-quarter')?.value || 'Q1';
      const releaseDate = dateParse.isoDate;
      const releaseTiming = row.querySelector('.earnings-calendar-timing')?.value || null;
      earningsCalendarStatusEl.textContent = `Saving ${symbol} calendar entry…`;
      earningsCalendarStatusEl.className = 'status';
      btn.disabled = true;
      try {
        const response = await fetch(`/api/earnings-review/calendar/${encodeURIComponent(entryId)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            fiscal_year: yearParse.year,
            fiscal_quarter: fiscalQuarter,
            release_date: releaseDate || null,
            release_timing: releaseTiming || null,
          }),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to save earnings calendar entry.'));
        earningsCalendarStatusEl.textContent = `Saved ${symbol} ${yearParse.year} ${fiscalQuarter}.`;
        earningsCalendarStatusEl.className = 'status';
        if (payload.item) {
          const index = earningsCalendarItems.findIndex((entry) => String(entry.id) === String(entryId));
          if (index >= 0) earningsCalendarItems[index] = payload.item;
        }
        renderEarningsCalendarTable();
      } catch (error) {
        earningsCalendarStatusEl.textContent = `Error: ${error.message}`;
        earningsCalendarStatusEl.className = 'status error';
      } finally {
        btn.disabled = false;
      }
    });
  });
  earningsCalendarTableBody.querySelectorAll('.earnings-calendar-symbol-link').forEach((btn) => {
    btn.addEventListener('click', async () => openAnalysisDetailForSymbol(btn.dataset.symbol, { origin: 'earnings_review' }));
  });
  earningsCalendarTableBody.querySelectorAll('.earnings-calendar-remove-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const entryId = btn.dataset.entryId;
      const symbol = btn.dataset.symbol || 'entry';
      if (!entryId) return;
      const confirmed = window.confirm(`Remove ${symbol} from Earnings Calendar?\n\nThis will only remove this quarter-specific calendar entry. Analysis, Earnings Reviews, Alerts, and other data are kept.`);
      if (!confirmed) return;
      earningsCalendarStatusEl.textContent = `Removing ${symbol} calendar entry…`;
      earningsCalendarStatusEl.className = 'status';
      btn.disabled = true;
      try {
        const response = await fetch(`/api/earnings-review/calendar/${encodeURIComponent(entryId)}`, {
          method: 'DELETE',
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to remove calendar entry.'));
        earningsCalendarStatusEl.textContent = `${symbol} calendar entry removed.`;
        earningsCalendarStatusEl.className = 'status';
        await loadEarningsCalendar();
      } catch (error) {
        earningsCalendarStatusEl.textContent = `Error: ${error.message}`;
        earningsCalendarStatusEl.className = 'status error';
      } finally {
        btn.disabled = false;
      }
    });
  });
}

async function createEarningsCalendarEntry() {
  const symbol = (earningsCalendarAddSymbolEl.value || '').trim().toUpperCase();
  if (!symbol) {
    earningsCalendarStatusEl.textContent = 'Error: Symbol is required.';
    earningsCalendarStatusEl.className = 'status error';
    earningsCalendarAddSymbolEl.focus();
    return;
  }
  const yearParse = parseEarningsCalendarFiscalYear(earningsCalendarAddFiscalYearEl.value || '');
  if (!yearParse.ok) {
    earningsCalendarStatusEl.textContent = `Error: ${yearParse.error}`;
    earningsCalendarStatusEl.className = 'status error';
    earningsCalendarAddFiscalYearEl.classList.add('input-error');
    earningsCalendarAddFiscalYearEl.focus();
    return;
  }
  earningsCalendarAddFiscalYearEl.classList.remove('input-error');
  const dateParse = parseCalendarDisplayDateToIso(earningsCalendarAddReleaseDateEl.value || '');
  if (!dateParse.ok) {
    earningsCalendarStatusEl.textContent = `Error: ${dateParse.error}`;
    earningsCalendarStatusEl.className = 'status error';
    earningsCalendarAddReleaseDateEl.classList.add('input-error');
    earningsCalendarAddReleaseDateEl.focus();
    return;
  }
  earningsCalendarAddReleaseDateEl.classList.remove('input-error');
  const fiscalQuarter = earningsCalendarAddFiscalQuarterEl.value || 'Q1';
  const releaseTiming = earningsCalendarAddReleaseTimingEl.value || null;
  earningsCalendarStatusEl.textContent = `Adding ${symbol} ${yearParse.year} ${fiscalQuarter}…`;
  earningsCalendarStatusEl.className = 'status';
  earningsCalendarAddBtn.disabled = true;
  try {
    const response = await fetch('/api/earnings-review/calendar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol,
        fiscal_year: yearParse.year,
        fiscal_quarter: fiscalQuarter,
        release_date: dateParse.isoDate || null,
        release_timing: releaseTiming || null,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to add calendar entry.'));
    earningsCalendarStatusEl.textContent = `Added ${symbol} ${yearParse.year} ${fiscalQuarter}.`;
    earningsCalendarStatusEl.className = 'status';
    earningsCalendarAddSymbolEl.value = '';
    earningsCalendarAddReleaseDateEl.value = '';
    earningsCalendarAddReleaseTimingEl.value = '';
    applyEarningsCalendarEntryDefaults({ force: true });
    await loadEarningsCalendar();
  } catch (error) {
    earningsCalendarStatusEl.textContent = `Error: ${error.message}`;
    earningsCalendarStatusEl.className = 'status error';
  } finally {
    earningsCalendarAddBtn.disabled = false;
  }
}

async function loadEarningsCalendar() {
  applyEarningsCalendarEntryDefaults();
  earningsCalendarPortfolioFilterEl.value = earningsCalendarPortfolioFilter;
  setSelectedEarningsCalendarDateFilters(earningsCalendarDateFilters);
  earningsCalendarStatusEl.textContent = 'Loading calendar entries…';
  earningsCalendarStatusEl.className = 'status';
  try {
    const response = await fetch('/api/earnings-review/calendar');
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load earnings calendar.'));
    earningsCalendarItems = Array.isArray(payload.items) ? payload.items : [];
    renderEarningsCalendarTable();
  } catch (error) {
    earningsCalendarStatusEl.textContent = `Error: ${error.message}`;
    earningsCalendarStatusEl.className = 'status error';
  }
}

async function addEarningsReviewSymbol() {
  const raw = earningsReviewAddSymbolEl.value || '';
  const normalized = raw.trim().toUpperCase();
  if (!normalized) {
    earningsReviewStatusEl.textContent = 'Please enter a symbol.';
    earningsReviewStatusEl.className = 'status error';
    return;
  }
  earningsReviewStatusEl.textContent = `Adding ${normalized}…`;
  earningsReviewStatusEl.className = 'status';
  earningsReviewAddBtn.disabled = true;
  try {
    const response = await fetch('/api/earnings-review/symbols', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: normalized }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to add symbol.'));
    earningsReviewAddSymbolEl.value = '';
    await refreshEarningsReviewListOnly();
    earningsReviewStatusEl.textContent = `Added ${normalized} to Earnings Review.`;
    earningsReviewStatusEl.className = 'status';
  } catch (error) {
    earningsReviewStatusEl.textContent = `Error: ${error.message}`;
    earningsReviewStatusEl.className = 'status error';
  } finally {
    earningsReviewAddBtn.disabled = false;
  }
}

function renderEarningsReviewDocuments(documents) {
  earningsReviewDocumentsTableBody.innerHTML = '';
  (documents || []).forEach((doc) => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${doc.original_file_name || 'N/A'}</td>
      <td>${doc.document_type || 'Other'}</td>
      <td>${formatDateTime(doc.uploaded_at)}</td>
      <td><button class="symbol-link earnings-document-open-btn" data-doc-id="${doc.id}">Open</button></td>
      <td><button class="remove-btn earnings-document-delete-btn" data-doc-id="${doc.id}" data-name="${doc.original_file_name || ''}">Delete</button></td>
    `;
    earningsReviewDocumentsTableBody.appendChild(row);
  });
  earningsReviewDocumentsTableBody.querySelectorAll('.earnings-document-open-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (!earningsReviewSelectedSymbol || !earningsReviewSelectedRecordId) return;
      const url = `/api/earnings-review/${encodeURIComponent(earningsReviewSelectedSymbol)}/${encodeURIComponent(earningsReviewSelectedRecordId)}/documents/${encodeURIComponent(btn.dataset.docId)}/download`;
      window.open(url, '_blank');
    });
  });
  earningsReviewDocumentsTableBody.querySelectorAll('.earnings-document-delete-btn').forEach((btn) => {
    btn.addEventListener('click', () => deleteEarningsReviewDocument(btn.dataset.docId, btn.dataset.name));
  });
  earningsReviewDocumentsStatusEl.textContent = (documents || []).length
    ? `Showing ${(documents || []).length} document(s).`
    : 'No earnings documents uploaded yet.';
  earningsReviewDocumentsStatusEl.className = 'status';
}

async function uploadEarningsReviewDocument() {
  if (!earningsReviewSelectedSymbol || !earningsReviewSelectedRecordId) return;
  const file = earningsReviewDocumentFileEl.files && earningsReviewDocumentFileEl.files[0];
  if (!file) {
    earningsReviewDocumentsStatusEl.textContent = 'Please choose a file to upload.';
    earningsReviewDocumentsStatusEl.className = 'status error';
    return;
  }
  const formData = new FormData();
  formData.append('document_type', earningsReviewDocumentTypeEl.value);
  formData.append('file', file);
  earningsReviewDocumentUploadBtn.disabled = true;
  earningsReviewDocumentsStatusEl.textContent = 'Uploading document…';
  earningsReviewDocumentsStatusEl.className = 'status';
  try {
    const response = await fetch(`/api/earnings-review/${encodeURIComponent(earningsReviewSelectedSymbol)}/${encodeURIComponent(earningsReviewSelectedRecordId)}/documents`, {
      method: 'POST',
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to upload earnings document.'));
    earningsReviewDocumentFileEl.value = '';
    earningsReviewDocumentFileNameEl.textContent = 'No file chosen';
    earningsReviewDocumentsStatusEl.textContent = 'Document uploaded successfully.';
    await refreshEarningsReviewListOnly();
    await openEarningsReviewRecordDetail(earningsReviewSelectedSymbol, earningsReviewSelectedRecordId);
  } catch (error) {
    earningsReviewDocumentsStatusEl.textContent = `Error: ${error.message}`;
    earningsReviewDocumentsStatusEl.className = 'status error';
  } finally {
    earningsReviewDocumentUploadBtn.disabled = false;
  }
}

async function deleteEarningsReviewDocument(documentId, fileName) {
  if (!earningsReviewSelectedSymbol || !earningsReviewSelectedRecordId || !documentId) return;
  const confirmed = window.confirm(
    `Delete Earnings Document\n\nAre you sure you want to delete this document${fileName ? ` (${fileName})` : ''}? This action cannot be undone.`
  );
  if (!confirmed) return;
  earningsReviewDocumentsStatusEl.textContent = 'Deleting document…';
  earningsReviewDocumentsStatusEl.className = 'status';
  try {
    const response = await fetch(`/api/earnings-review/${encodeURIComponent(earningsReviewSelectedSymbol)}/${encodeURIComponent(earningsReviewSelectedRecordId)}/documents/${encodeURIComponent(documentId)}`, {
      method: 'DELETE',
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to delete earnings document.'));
    earningsReviewDocumentsStatusEl.textContent = 'Document deleted successfully.';
    await refreshEarningsReviewListOnly();
    await openEarningsReviewRecordDetail(earningsReviewSelectedSymbol, earningsReviewSelectedRecordId);
  } catch (error) {
    earningsReviewDocumentsStatusEl.textContent = `Error: ${error.message}`;
    earningsReviewDocumentsStatusEl.className = 'status error';
  }
}

function renderEarningsKeyVariables(variables) {
  earningsReviewKeyVariablesBody.innerHTML = '';
  (variables || []).forEach((item) => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${item.variable || 'N/A'}</td>
      <td>${item.type || 'N/A'}</td>
      <td>${normalizeDriverCategory(item.driver_category)}</td>
      <td>${typeof item.confidence === 'number' ? item.confidence : 'N/A'}</td>
      <td>${typeof item.importance === 'number' ? item.importance : 'N/A'}</td>
    `;
    earningsReviewKeyVariablesBody.appendChild(row);
  });
}

function getWatchpointResultMap(results) {
  const mapped = new Map();
  (results || []).forEach((item) => {
    const key = `${item.key_variable_text || ''}::${item.watchpoint_text || ''}`;
    mapped.set(key, item);
  });
  return mapped;
}

function statusBadgeClass(status) {
  if (status === 'Confirmed') return 'watchpoint-badge confirmed';
  if (status === 'Partially confirmed') return 'watchpoint-badge partially-confirmed';
  if (status === 'Contradicted') return 'watchpoint-badge contradicted';
  if (status === 'Not addressed') return 'watchpoint-badge not-addressed';
  return 'watchpoint-badge unclear';
}

function renderEarningsWatchpoints(groups, results) {
  earningsReviewWatchpointsEl.innerHTML = '';
  if (!Array.isArray(groups) || groups.length === 0) {
    earningsReviewWatchpointsEl.innerHTML = '<p class="status">No earnings watchpoints generated yet for this symbol.</p>';
    return;
  }
  const resultMap = getWatchpointResultMap(results);
  groups.forEach((group) => {
    const card = document.createElement('div');
    card.className = 'watchpoint-group';
    const watchpoints = Array.isArray(group.watchpoints) ? group.watchpoints : [];
    const listHtml = watchpoints.map((item) => {
      const result = resultMap.get(`${group.key_variable || ''}::${item}`);
      if (!result) {
        return `<li class="watchpoint-item"><div class="watchpoint-text">${item}</div></li>`;
      }
      return `
        <li class="watchpoint-item">
          <div class="watchpoint-row">
            <div class="watchpoint-text">${item}</div>
            <span class="${statusBadgeClass(result.status)}">${result.status}</span>
          </div>
          <div class="watchpoint-result-text">${result.result_text || ''}</div>
        </li>
      `;
    }).join('');
    card.innerHTML = `
      <h5>Key Variable: ${group.key_variable || 'N/A'}</h5>
      <p class="status">Type: ${group.type || 'N/A'}</p>
      <ul class="clean-list">${listHtml}</ul>
    `;
    earningsReviewWatchpointsEl.appendChild(card);
  });
}

function renderEarningsReviewSymbolHistoryTable(records) {
  earningsReviewSymbolTableBody.innerHTML = '';
  (records || []).forEach((record) => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${record.fiscal_year}</td>
      <td>${record.fiscal_quarter}</td>
      <td>${formatDate(record.release_date)}</td>
      <td>${record.status || 'Draft'}</td>
      <td>${formatDateTime(record.created_at)}</td>
      <td>${formatDateTime(record.updated_at)}</td>
      <td>${typeof record.watchpoints_count === 'number' ? record.watchpoints_count : 0}</td>
      <td><button class="symbol-link earnings-record-open-btn" data-review-id="${record.id}">Open</button></td>
      <td><button class="remove-btn earnings-record-delete-btn" data-review-id="${record.id}" data-fiscal-year="${record.fiscal_year}" data-fiscal-quarter="${record.fiscal_quarter}">Delete</button></td>
    `;
    earningsReviewSymbolTableBody.appendChild(row);
  });
  earningsReviewSymbolTableBody.querySelectorAll('.earnings-record-open-btn').forEach((btn) => {
    btn.addEventListener('click', () => openEarningsReviewRecordDetail(earningsReviewSelectedSymbol, Number(btn.dataset.reviewId)));
  });
  earningsReviewSymbolTableBody.querySelectorAll('.earnings-record-delete-btn').forEach((btn) => {
    btn.addEventListener('click', () => deleteEarningsReviewRecord({
      reviewId: Number(btn.dataset.reviewId),
      fiscalYear: btn.dataset.fiscalYear,
      fiscalQuarter: btn.dataset.fiscalQuarter,
    }));
  });
}

function showEarningsReviewSymbolHistoryView() {
  earningsReviewListView.classList.add('hidden');
  earningsReviewSymbolView.classList.remove('hidden');
  earningsReviewDetailView.classList.add('hidden');
}

async function openEarningsReviewSymbolHistory(symbol) {
  const normalized = (symbol || '').trim().toUpperCase();
  if (!normalized) return;
  setEarningsReviewTab('workflow');
  earningsReviewSelectedSymbol = normalized;
  earningsReviewSelectedRecordId = null;
  showEarningsReviewSymbolHistoryView();
  earningsReviewSymbolTitleEl.textContent = `Earnings History: ${normalized}`;
  earningsReviewSymbolHeaderEl.textContent = `Loading ${normalized} earnings history…`;
  earningsReviewSymbolStatusEl.textContent = 'Loading earnings history…';
  earningsReviewSymbolStatusEl.className = 'status';
  earningsReviewSymbolTableBody.innerHTML = '';
  try {
    const response = await fetch(`/api/earnings-review/${encodeURIComponent(normalized)}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load earnings history.'));
    const item = payload.item || {};
    earningsReviewSymbolHistory = item;
    earningsReviewSymbolHeaderEl.textContent = `${item.symbol || normalized} — ${item.company_name || 'Unknown company'}`;
    renderEarningsReviewSymbolHistoryTable(item.records || []);
    earningsReviewSymbolStatusEl.textContent = (item.records || []).length
      ? `Showing ${(item.records || []).length} earnings review record(s).`
      : 'No earnings reviews created yet. Create the first one to begin this symbol history.';
  } catch (error) {
    earningsReviewSymbolStatusEl.textContent = `Error: ${error.message}`;
    earningsReviewSymbolStatusEl.className = 'status error';
  }
}

async function refreshEarningsReviewListOnly() {
  const response = await fetch('/api/earnings-review');
  const payload = await response.json();
  if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load earnings review list.'));
  earningsReviewItems = Array.isArray(payload.items) ? payload.items : [];
  renderEarningsReviewList();
}

async function loadEarningsReview() {
  if (earningsReviewActiveTab === 'calendar') {
    setEarningsReviewTab('calendar');
    await loadEarningsCalendar();
    return;
  }
  setEarningsReviewTab('workflow');
  showEarningsReviewList();
  earningsReviewSymbolView.classList.add('hidden');
  earningsReviewDetailView.classList.add('hidden');
  toggleEarningsReviewCreateForm(false);
  earningsReviewStatusEl.textContent = 'Loading symbols…';
  earningsReviewStatusEl.className = 'status';
  earningsReviewGenerateBtn.disabled = true;
  try {
    await refreshEarningsReviewListOnly();
    if (!earningsReviewItems.length) {
      earningsReviewStatusEl.textContent = 'No symbols in Earnings Review yet. Add a symbol to begin.';
      return;
    }
  } catch (error) {
    earningsReviewStatusEl.textContent = `Error: ${error.message}`;
    earningsReviewStatusEl.className = 'status error';
  }
}

function toggleEarningsReviewCreateForm(show) {
  earningsReviewCreateForm.classList.toggle('hidden', !show);
  if (show) {
    const now = new Date();
    earningsReviewCreateYearEl.value = String(now.getUTCFullYear());
    earningsReviewCreateQuarterEl.value = 'Q1';
    earningsReviewCreateReleaseDateEl.value = '';
  }
}

async function createEarningsReviewRecord() {
  if (!earningsReviewSelectedSymbol) return;
  const payload = {
    fiscal_year: Number(earningsReviewCreateYearEl.value),
    fiscal_quarter: earningsReviewCreateQuarterEl.value,
    release_date: earningsReviewCreateReleaseDateEl.value || null,
  };
  earningsReviewSymbolStatusEl.textContent = 'Creating earnings review record…';
  earningsReviewSymbolStatusEl.className = 'status';
  earningsReviewCreateSubmitBtn.disabled = true;
  try {
    const response = await fetch(`/api/earnings-review/${encodeURIComponent(earningsReviewSelectedSymbol)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(result, 'Unable to create earnings review record.'));
    toggleEarningsReviewCreateForm(false);
    await openEarningsReviewRecordDetail(earningsReviewSelectedSymbol, Number(result.item?.id));
  } catch (error) {
    earningsReviewSymbolStatusEl.textContent = `Error: ${error.message}`;
    earningsReviewSymbolStatusEl.className = 'status error';
  } finally {
    earningsReviewCreateSubmitBtn.disabled = false;
  }
}

async function deleteEarningsReviewRecord({ reviewId, fiscalYear, fiscalQuarter }) {
  if (!earningsReviewSelectedSymbol || !Number.isFinite(reviewId)) return;
  const confirmed = window.confirm(
    `Delete Earnings Review\n\nAre you sure you want to delete this earnings review for FY${fiscalYear} ${fiscalQuarter}? This action cannot be undone.`
  );
  if (!confirmed) return;
  earningsReviewSymbolStatusEl.textContent = 'Deleting earnings review record…';
  earningsReviewSymbolStatusEl.className = 'status';
  try {
    const response = await fetch(`/api/earnings-review/${encodeURIComponent(earningsReviewSelectedSymbol)}/${encodeURIComponent(reviewId)}`, {
      method: 'DELETE',
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Failed to delete earnings review. Please try again.'));
    await openEarningsReviewSymbolHistory(earningsReviewSelectedSymbol);
  } catch (_error) {
    earningsReviewSymbolStatusEl.textContent = 'Failed to delete earnings review. Please try again.';
    earningsReviewSymbolStatusEl.className = 'status error';
  }
}

function renderEarningsSnapshotSummary(snapshot, detail) {
  const rating = snapshot?.rating || 'N/A';
  const currentPrice = formatCurrencyValue(snapshot?.current_price, 'USD');
  const expectedPrice = formatCurrencyValue(snapshot?.expected_price, 'USD');
  const upside = formatPercent(snapshot?.upside);
  const businessModel = escapeHtml(snapshot?.business_model || '');
  const businessSummary = escapeHtml(snapshot?.business_summary || '');
  earningsReviewSnapshotSummaryEl.innerHTML = `
    <div class="summary-grid">
      <div class="summary-item"><div class="label">Status</div><div class="value">${detail.status || 'Draft'}</div></div>
      <div class="summary-item"><div class="label">Fiscal Period</div><div class="value">${detail.fiscal_year} ${detail.fiscal_quarter}</div></div>
      <div class="summary-item"><div class="label">Release Date</div><div class="value">${formatDate(detail.release_date)}</div></div>
      <div class="summary-item"><div class="label">Rating Snapshot</div><div class="value">${rating}</div></div>
      <div class="summary-item"><div class="label">Current Price Snapshot</div><div class="value">${currentPrice}</div></div>
      <div class="summary-item"><div class="label">Expected Price Snapshot</div><div class="value">${expectedPrice}</div></div>
      <div class="summary-item"><div class="label">Upside Snapshot</div><div class="value">${upside}</div></div>
    </div>
    <p><strong>Business Model Snapshot:</strong> ${businessModel || 'N/A'}</p>
    <p><strong>Business Summary Snapshot:</strong> ${businessSummary || 'N/A'}</p>
  `;
}

async function openEarningsReviewRecordDetail(symbol, reviewId) {
  const normalized = (symbol || '').trim().toUpperCase();
  if (!normalized || !Number.isFinite(reviewId)) return;
  setEarningsReviewTab('workflow');
  earningsReviewSelectedSymbol = normalized;
  earningsReviewSelectedRecordId = Number(reviewId);
  showEarningsReviewDetail();
  earningsReviewDetailTitleEl.textContent = `Loading ${normalized} review…`;
  earningsReviewDetailHeaderEl.textContent = `Loading review detail…`;
  earningsReviewDetailMetaEl.textContent = 'Loading earnings review record…';
  earningsReviewDetailMetaEl.className = 'status';
  earningsReviewGenerateBtn.disabled = true;
  earningsReviewAnalyseBtn.disabled = true;
  earningsReviewKeyVariablesBody.innerHTML = '';
  earningsReviewWatchpointsEl.innerHTML = '';
  earningsReviewSnapshotSummaryEl.innerHTML = '';
  earningsReviewDocumentsTableBody.innerHTML = '';
  earningsReviewDocumentsStatusEl.textContent = 'Loading documents…';
  earningsReviewDocumentsStatusEl.className = 'status';
  earningsReviewDocumentFileEl.value = '';
  earningsReviewDocumentFileNameEl.textContent = 'No file chosen';
  try {
    const response = await fetch(`/api/earnings-review/${encodeURIComponent(normalized)}/${encodeURIComponent(earningsReviewSelectedRecordId)}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load earnings review record.'));
    const item = payload.item || {};
    const snapshot = item.thesis_snapshot || {};
    earningsReviewDetailTitleEl.textContent = `Earnings Review: ${item.symbol} ${item.fiscal_year} ${item.fiscal_quarter}`;
    earningsReviewDetailHeaderEl.textContent = `${item.symbol} — ${item.company_name_snapshot || snapshot.company_name || item.symbol}`;
    earningsReviewDetailMetaEl.textContent = `Status: ${item.status || 'Draft'} • Release Date: ${formatDate(item.release_date)} • Watchpoints generated: ${item.watchpoints_generated_at ? formatDateTime(item.watchpoints_generated_at) : 'Not yet generated'} • Updated: ${formatDateTime(item.updated_at)}`;
    const hasWatchpoints = Array.isArray(item.watchpoints_by_variable) && item.watchpoints_by_variable.length > 0;
    const hasDocuments = Array.isArray(item.documents) && item.documents.length > 0;
    earningsReviewGenerateBtn.textContent = hasWatchpoints
      ? 'Regenerate Earnings Watchpoints from Key Variables'
      : 'Generate Earnings Watchpoints from Key Variables';
    earningsReviewGenerateBtn.disabled = false;
    earningsReviewAnalyseBtn.disabled = !(hasWatchpoints && hasDocuments);
    renderEarningsSnapshotSummary(snapshot, item);
    renderEarningsKeyVariables(item.key_variables_snapshot || []);
    renderEarningsWatchpoints(item.watchpoints_by_variable || [], item.watchpoint_results || []);
    renderEarningsReviewDocuments(item.documents || []);
  } catch (error) {
    earningsReviewDetailMetaEl.textContent = `Error: ${error.message}`;
    earningsReviewDetailMetaEl.className = 'status error';
    earningsReviewDocumentsStatusEl.textContent = `Error: ${error.message}`;
    earningsReviewDocumentsStatusEl.className = 'status error';
  }
}

async function generateEarningsWatchpoints() {
  if (!earningsReviewSelectedSymbol || !earningsReviewSelectedRecordId) return;
  const targetSymbol = earningsReviewSelectedSymbol;
  const targetReviewId = earningsReviewSelectedRecordId;
  earningsReviewGenerateBtn.disabled = true;
  earningsReviewDetailMetaEl.textContent = `Generating earnings watchpoints for ${targetSymbol} ${targetReviewId}…`;
  earningsReviewDetailMetaEl.className = 'status';
  try {
    const response = await fetch(`/api/earnings-review/${encodeURIComponent(targetSymbol)}/${encodeURIComponent(targetReviewId)}/generate-watchpoints`, {
      method: 'POST',
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to generate earnings watchpoints.'));
    earningsReviewDetailMetaEl.textContent = 'Earnings watchpoints generated successfully.';
    await refreshEarningsReviewListOnly();
    await openEarningsReviewRecordDetail(targetSymbol, targetReviewId);
  } catch (error) {
    earningsReviewDetailMetaEl.textContent = `Error: ${error.message}`;
    earningsReviewDetailMetaEl.className = 'status error';
    earningsReviewGenerateBtn.disabled = false;
  }
}

async function analyseEarningsWatchpoints() {
  if (!earningsReviewSelectedSymbol || !earningsReviewSelectedRecordId) return;
  const targetSymbol = earningsReviewSelectedSymbol;
  const targetReviewId = earningsReviewSelectedRecordId;
  earningsReviewAnalyseBtn.disabled = true;
  earningsReviewDetailMetaEl.textContent = `Analysing earnings watchpoints for ${targetSymbol} ${targetReviewId}…`;
  earningsReviewDetailMetaEl.className = 'status';
  try {
    const response = await fetch(`/api/earnings-review/${encodeURIComponent(targetSymbol)}/${encodeURIComponent(targetReviewId)}/analyse-watchpoints`, {
      method: 'POST',
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to analyse earnings watchpoints.'));
    earningsReviewDetailMetaEl.textContent = 'Earnings watchpoints analysed successfully.';
    await refreshEarningsReviewListOnly();
    await openEarningsReviewRecordDetail(targetSymbol, targetReviewId);
  } catch (error) {
    earningsReviewDetailMetaEl.textContent = `Error: ${error.message}`;
    earningsReviewDetailMetaEl.className = 'status error';
    earningsReviewAnalyseBtn.disabled = false;
  }
}


async function loadPromptConfiguration() {
  promptStatusEl.textContent = 'Loading prompt configuration…';
  promptStatusEl.className = 'status';
  try { const response = await fetch('/api/configuration/prompts'); const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load prompt configuration'));
    const templates = payload.templates || {}; const sources = payload.sources || {};
    promptBusinessModelEl.value = templates.analysis_prompt_business_model || '';
    promptKeyVariablesEl.value = templates.analysis_prompt_key_variables || '';
    promptScenariosEl.value = templates.analysis_prompt_scenarios || '';
    promptRecentEventCandidatesEl.value = templates.analysis_prompt_recent_event_candidate || '';
    promptRecentEventsEl.value = templates.analysis_prompt_recent_event_check || '';
    promptEarningsWatchpointsEl.value = templates.earnings_watchpoints || '';
    promptEarningsWatchpointAnalysisEl.value = templates.earnings_watchpoint_analysis || '';
    promptStatusEl.textContent = `Loaded prompt templates (business=${sources.analysis_prompt_business_model || 'default'}, key=${sources.analysis_prompt_key_variables || 'default'}, scenarios=${sources.analysis_prompt_scenarios || 'default'}, recent-event-candidates=${sources.analysis_prompt_recent_event_candidate || 'default'}, recent-events=${sources.analysis_prompt_recent_event_check || 'default'}, earnings-watchpoints=${sources.earnings_watchpoints || 'default'}, earnings-watchpoint-analysis=${sources.earnings_watchpoint_analysis || 'default'}).`;
  } catch (error) { promptStatusEl.textContent = `Error: ${error.message}`; promptStatusEl.className = 'status error'; }
}

async function savePromptConfiguration() {
  promptStatusEl.textContent = 'Saving prompts…'; promptStatusEl.className = 'status';
  try { const response = await fetch('/api/configuration/prompts', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ templates: { analysis_prompt_business_model: promptBusinessModelEl.value, analysis_prompt_key_variables: promptKeyVariablesEl.value, analysis_prompt_scenarios: promptScenariosEl.value, analysis_prompt_recent_event_candidate: promptRecentEventCandidatesEl.value.trim(), analysis_prompt_recent_event_check: promptRecentEventsEl.value.trim(), earnings_watchpoints: promptEarningsWatchpointsEl.value.trim(), earnings_watchpoint_analysis: promptEarningsWatchpointAnalysisEl.value.trim() } }) });
    const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to save prompts')); promptStatusEl.textContent = 'Prompts saved.';
  } catch (error) { promptStatusEl.textContent = `Error: ${error.message}`; promptStatusEl.className = 'status error'; }
}

async function resetPromptConfiguration() {
  promptStatusEl.textContent = 'Restoring default prompts…'; promptStatusEl.className = 'status';
  try { const response = await fetch('/api/configuration/prompts/reset', { method: 'POST' }); const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to reset prompts'));
    const templates = payload.templates || {}; promptBusinessModelEl.value = templates.analysis_prompt_business_model || ''; promptKeyVariablesEl.value = templates.analysis_prompt_key_variables || ''; promptScenariosEl.value = templates.analysis_prompt_scenarios || ''; promptRecentEventCandidatesEl.value = templates.analysis_prompt_recent_event_candidate || ''; promptRecentEventsEl.value = templates.analysis_prompt_recent_event_check || ''; promptEarningsWatchpointsEl.value = templates.earnings_watchpoints || ''; promptEarningsWatchpointAnalysisEl.value = templates.earnings_watchpoint_analysis || '';
    promptStatusEl.textContent = 'Default prompts restored.';
  } catch (error) { promptStatusEl.textContent = `Error: ${error.message}`; promptStatusEl.className = 'status error'; }
}

async function previewPromptConfiguration() {
  const symbol = promptPreviewSymbolInput.value.trim().toUpperCase(); if (!symbol) { promptPreviewOutput.textContent = 'Enter a symbol to preview.'; return; }
  promptPreviewOutput.textContent = 'Rendering preview…';
  try { const response = await fetch('/api/configuration/prompts/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol }) });
    const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to preview prompt'));
    const rendered = payload.rendered_prompts || {}; promptPreviewOutput.textContent = `Symbol: ${payload.symbol}
Price: ${payload.price}

[Business Model Prompt]
${rendered.analysis_prompt_business_model || ''}

[Key Variables Prompt]
${rendered.analysis_prompt_key_variables || ''}

[Scenarios Prompt]
${rendered.analysis_prompt_scenarios || ''}

[Recent Event Candidate Prompt]
${rendered.analysis_prompt_recent_event_candidate || ''}

[Recent Event Check Prompt]
${rendered.analysis_prompt_recent_event_check || ''}

[Earnings Watchpoints Prompt]
${rendered.earnings_watchpoints || ''}

[Earnings Watchpoint Analysis Prompt]
${rendered.earnings_watchpoint_analysis || ''}`;
  } catch (error) { promptPreviewOutput.textContent = `Error: ${error.message}`; }
}

function getScenarioProbabilitySettingsFromForm() {
  return {
    probability_source_mode: (configScenarioProbabilitySourceModeEl.value || 'hybrid').toLowerCase(),
    hybrid_ai_weight: Number(configScenarioProbabilityHybridAiWeightEl.value),
    hybrid_backend_weight: Number(configScenarioProbabilityHybridBackendWeightEl.value),
    backend_base_max_probability: Number(configScenarioProbabilityBackendBaseMaxEl.value),
    backend_base_min_probability: Number(configScenarioProbabilityBackendBaseMinEl.value),
  };
}

function applyScenarioProbabilitySettingsToForm(settings) {
  const effective = { ...DEFAULT_SCENARIO_PROBABILITY_SETTINGS, ...(settings || {}) };
  configScenarioProbabilitySourceModeEl.value = String(effective.probability_source_mode || 'hybrid').toLowerCase();
  configScenarioProbabilityHybridAiWeightEl.value = effective.hybrid_ai_weight;
  configScenarioProbabilityHybridBackendWeightEl.value = effective.hybrid_backend_weight;
  configScenarioProbabilityBackendBaseMaxEl.value = effective.backend_base_max_probability;
  configScenarioProbabilityBackendBaseMinEl.value = effective.backend_base_min_probability;
}

function validateScenarioProbabilitySettings(settings) {
  if (!['ai', 'backend', 'hybrid'].includes(settings.probability_source_mode)) {
    return 'probability_source_mode must be AI, Backend, or Hybrid.';
  }
  if (!Number.isFinite(settings.hybrid_ai_weight) || settings.hybrid_ai_weight < 0) {
    return 'hybrid_ai_weight must be numeric and >= 0.';
  }
  if (!Number.isFinite(settings.hybrid_backend_weight) || settings.hybrid_backend_weight < 0) {
    return 'hybrid_backend_weight must be numeric and >= 0.';
  }
  if (!Number.isFinite(settings.backend_base_max_probability) || settings.backend_base_max_probability < 0 || settings.backend_base_max_probability > 100) {
    return 'backend_base_max_probability must be between 0 and 100.';
  }
  if (!Number.isFinite(settings.backend_base_min_probability) || settings.backend_base_min_probability < 0 || settings.backend_base_min_probability > 100) {
    return 'backend_base_min_probability must be between 0 and 100.';
  }
  return null;
}

function getRatingSettingsFromForm() {
  return {
    min_conviction_hold_threshold: Number(configRatingMinConvictionHoldThresholdEl.value),
    strong_buy_min_upside: Number(configRatingStrongBuyMinUpsideEl.value),
    strong_buy_min_diff: Number(configRatingStrongBuyMinDiffEl.value),
    strong_buy_min_bullish_confidence: Number(configRatingStrongBuyMinBullishConfidenceEl.value),
    buy_min_upside: Number(configRatingBuyMinUpsideEl.value),
    buy_min_diff: Number(configRatingBuyMinDiffEl.value),
    buy_min_bullish_confidence: Number(configRatingBuyMinBullishConfidenceEl.value),
    speculative_buy_min_upside: Number(configRatingSpeculativeBuyMinUpsideEl.value),
    speculative_buy_min_diff: Number(configRatingSpeculativeBuyMinDiffEl.value),
    speculative_buy_min_bullish_confidence: Number(configRatingSpeculativeBuyMinBullishConfidenceEl.value),
    speculative_buy_min_core_diff_floor: Number(configRatingSpeculativeBuyMinCoreDiffFloorEl.value),
    strong_sell_max_upside: Number(configRatingStrongSellMaxUpsideEl.value),
    strong_sell_max_diff: Number(configRatingStrongSellMaxDiffEl.value),
    strong_sell_min_bearish_confidence: Number(configRatingStrongSellMinBearishConfidenceEl.value),
    sell_max_upside: Number(configRatingSellMaxUpsideEl.value),
    sell_max_diff: Number(configRatingSellMaxDiffEl.value),
    sell_min_bearish_confidence: Number(configRatingSellMinBearishConfidenceEl.value),
  };
}

function applyRatingSettingsToForm(settings) {
  const effective = { ...DEFAULT_RATING_SETTINGS, ...(settings || {}) };
  configRatingMinConvictionHoldThresholdEl.value = effective.min_conviction_hold_threshold;
  configRatingStrongBuyMinUpsideEl.value = effective.strong_buy_min_upside;
  configRatingStrongBuyMinDiffEl.value = effective.strong_buy_min_diff;
  configRatingStrongBuyMinBullishConfidenceEl.value = effective.strong_buy_min_bullish_confidence;
  configRatingBuyMinUpsideEl.value = effective.buy_min_upside;
  configRatingBuyMinDiffEl.value = effective.buy_min_diff;
  configRatingBuyMinBullishConfidenceEl.value = effective.buy_min_bullish_confidence;
  configRatingSpeculativeBuyMinUpsideEl.value = effective.speculative_buy_min_upside;
  configRatingSpeculativeBuyMinDiffEl.value = effective.speculative_buy_min_diff;
  configRatingSpeculativeBuyMinBullishConfidenceEl.value = effective.speculative_buy_min_bullish_confidence;
  configRatingSpeculativeBuyMinCoreDiffFloorEl.value = effective.speculative_buy_min_core_diff_floor;
  configRatingStrongSellMaxUpsideEl.value = effective.strong_sell_max_upside;
  configRatingStrongSellMaxDiffEl.value = effective.strong_sell_max_diff;
  configRatingStrongSellMinBearishConfidenceEl.value = effective.strong_sell_min_bearish_confidence;
  configRatingSellMaxUpsideEl.value = effective.sell_max_upside;
  configRatingSellMaxDiffEl.value = effective.sell_max_diff;
  configRatingSellMinBearishConfidenceEl.value = effective.sell_min_bearish_confidence;
}

function validateRatingSettings(settings) {
  const confidenceKeys = [
    'min_conviction_hold_threshold',
    'strong_buy_min_bullish_confidence',
    'buy_min_bullish_confidence',
    'speculative_buy_min_bullish_confidence',
    'strong_sell_min_bearish_confidence',
    'sell_min_bearish_confidence',
  ];
  for (const [key, value] of Object.entries(settings)) {
    if (!Number.isFinite(value)) return `${key} must be numeric.`;
    if (confidenceKeys.includes(key) && (value < 0 || value > 10)) return `${key} must be between 0 and 10.`;
  }
  return null;
}

function getActionPlanSettingsFromForm() {
  const settings = {};
  configActionPlanInputs.forEach((input) => {
    const key = input.dataset.actionPlanSetting;
    if (input.type === 'checkbox') settings[key] = input.checked;
    else if (input.type === 'text') settings[key] = input.value;
    else settings[key] = Number(input.value);
  });
  return settings;
}

function applyActionPlanSettingsToForm(settings) {
  const effective = { ...DEFAULT_ACTION_PLAN_SETTINGS, ...(settings || {}) };
  configActionPlanInputs.forEach((input) => {
    const key = input.dataset.actionPlanSetting;
    if (input.type === 'checkbox') input.checked = Boolean(effective[key]);
    else input.value = effective[key];
  });
  updateActionPlanBucketTotal();
}

function updateActionPlanBucketTotal() {
  if (!configActionPlanTotalEl) return;
  const settings = getActionPlanSettingsFromForm();
  const total = ['action_bucket_strong_buy_target', 'action_bucket_buy_target', 'action_bucket_speculative_buy_target', 'action_bucket_hold_target', 'action_bucket_cash_target', 'action_bucket_sell_target', 'action_bucket_strong_sell_target']
    .reduce((sum, key) => sum + (Number.isFinite(settings[key]) ? settings[key] : 0), 0);
  const dynamicEnabled = Boolean(settings.action_use_dynamic_bucket_sizing);
  configActionPlanTotalEl.textContent = dynamicEnabled
    ? 'Fixed bucket targets are used only when Dynamic Bucket Sizing is off.'
    : `Bucket total: ${formatPercent(total)}`;
  configActionPlanTotalEl.className = (!dynamicEnabled && total > 100) ? 'status error' : 'status';
  document.querySelectorAll('[data-fixed-bucket-setting="true"]').forEach((el) => {
    el.classList.toggle('hidden', dynamicEnabled);
    const input = el.querySelector('input');
    if (input) input.disabled = dynamicEnabled;
  });
}

function validateActionPlanSettings(settings) {
  for (const [key, value] of Object.entries(settings)) {
    if (typeof value === 'boolean') continue;
    if (key === 'action_cash_equivalent_symbols') continue;
    if (!Number.isFinite(value)) return `${key} must be numeric.`;
    if (value < 0 && !['action_core_diff_zero_score', 'action_core_diff_full_score', 'action_trim_remaining_upside_threshold', 'action_sell_remaining_upside_threshold', 'linear_reserve_benchmark_yield_pct', 'linear_min_equity_excess_cagr_pct', 'linear_full_attractiveness_equity_excess_cagr_pct', 'linear_min_core_net', 'linear_min_potential_net', 'core_confidence_penalty_threshold', 'potential_confidence_penalty_threshold', 'linear_strong_buy_rating_bonus', 'linear_buy_rating_bonus', 'linear_score_allocation_power', 'linear_add_band_tolerance_pct', 'linear_trim_band_tolerance_pct'].includes(key)) return `${key} cannot be negative.`;
  }
  const bucketTotal = ['action_bucket_strong_buy_target', 'action_bucket_buy_target', 'action_bucket_speculative_buy_target', 'action_bucket_hold_target', 'action_bucket_cash_target', 'action_bucket_sell_target', 'action_bucket_strong_sell_target']
    .reduce((sum, key) => sum + settings[key], 0);
  if (!settings.action_use_dynamic_bucket_sizing && bucketTotal > 100) return 'Action Plan bucket targets cannot total more than 100%.';
  if (settings.action_min_cash_unallocated_target < 0 || settings.action_min_cash_unallocated_target > 100) return 'Minimum cash/unallocated target must be between 0 and 100%.';
  if (settings.action_use_dynamic_bucket_sizing) {
    if (settings.action_min_cash_unallocated_target < 0 || settings.action_min_cash_unallocated_target > 50) return 'Minimum cash/unallocated target must be between 0 and 50%.';
    if (settings.action_weighted_count_full_score <= settings.action_weighted_count_min_score) return 'Weighted count full score must be greater than minimum score.';
    if (settings.action_weighted_count_min_score < 0 || settings.action_weighted_count_full_score > 1) return 'Weighted count score thresholds must be between 0 and 1.';
    if (settings.action_weighted_count_max_contribution <= 0 || settings.action_weighted_count_max_contribution > 1) return 'Weighted count max contribution must be > 0 and <= 1.';
    if (settings.action_max_potential_score_contribution < 0 || settings.action_max_potential_score_contribution > 1) return 'Max potential score contribution must be between 0 and 1.';
    const allocationWeightTotal = settings.action_allocation_upside_weight + settings.action_allocation_core_weight + settings.action_allocation_potential_weight;
    if (allocationWeightTotal <= 0) return 'Allocation weights must total more than 0.';
    if (settings.action_allocation_risk_penalty_strength < 0 || settings.action_allocation_risk_penalty_strength > 1) return 'Allocation risk penalty strength must be between 0 and 1.';
    const bucketSizingWeightTotal = settings.action_bucket_sizing_upside_weight + settings.action_bucket_sizing_core_weight + settings.action_bucket_sizing_potential_weight;
    if (bucketSizingWeightTotal <= 0) return 'Bucket sizing weights must total more than 0.';
    if (settings.action_bucket_sizing_risk_penalty_strength < 0 || settings.action_bucket_sizing_risk_penalty_strength > 1) return 'Bucket sizing risk penalty strength must be between 0 and 1.';
  }
  if (settings.action_target_band_lower_multiplier < 0 || settings.action_target_band_lower_multiplier >= 1) return 'Target band lower multiplier must be >= 0 and < 1.';
  if (settings.action_target_band_upper_multiplier <= 1) return 'Target band upper multiplier must be greater than 1.';
  if (settings.action_upside_full_score <= settings.action_upside_zero_score) return 'Action Plan upside full score must be greater than zero score.';
  if (settings.action_core_diff_full_score <= settings.action_core_diff_zero_score) return 'Action Plan core diff full score must be greater than zero score.';
  if (settings.action_core_bearish_penalty_full <= settings.action_core_bearish_penalty_start) return 'Action Plan core bearish penalty full must be greater than start.';
  if (settings.action_potential_diff_full_score <= settings.action_potential_diff_minimum) return 'Action Plan potential diff full score must be greater than minimum.';
  for (const key of ['action_momentum_add_max_raise', 'action_momentum_add_max_lower', 'action_extension_add_max_lower', 'action_momentum_trim_max_raise', 'action_momentum_trim_max_lower', 'action_extension_trim_max_lower']) {
    if (settings[key] < 0 || settings[key] > 1) return `${key} must be between 0 and 1.`;
  }
  if (settings.action_min_trigger_multiplier <= 0 || settings.action_min_trigger_multiplier > 1) return 'Action min trigger multiplier must be > 0 and <= 1.';
  if (settings.action_max_trigger_multiplier < 1 || settings.action_max_trigger_multiplier > 2) return 'Action max trigger multiplier must be >= 1 and <= 2.';
  if (settings.action_max_trigger_multiplier <= settings.action_min_trigger_multiplier) return 'Action max trigger multiplier must be greater than min trigger multiplier.';
  for (const key of ['action_starter_buy_base_required_upside', 'action_add_base_required_upside', 'action_strong_add_base_required_upside', 'action_hold_extra_add_required_upside']) {
    if (settings[key] < 0 || settings[key] > 2) return `${key} must be between 0 and 2.`;
  }
  for (const key of ['core_confidence_penalty', 'upside_penalty', 'potential_confidence_penalty', 'hold_rating_penalty', 'linear_strong_buy_rating_bonus', 'linear_buy_rating_bonus']) {
    if (settings[key] < 0 || settings[key] > 1) return `${key} must be between 0 and 1.`;
  }
  if (settings.linear_full_core_net <= settings.linear_min_core_net) return 'linear_full_core_net must be greater than linear_min_core_net.';
  if (settings.linear_full_attractiveness_equity_excess_cagr_pct <= settings.linear_min_equity_excess_cagr_pct) return 'Linear full-attractiveness equity excess CAGR must be greater than the minimum equity excess CAGR.';
  if (settings.linear_max_reserve_pct < settings.action_min_cash_unallocated_target || settings.linear_max_reserve_pct > 100) return 'Linear maximum reserve must be between Minimum cash/unallocated and 100%.';
  if (settings.linear_full_potential_net <= settings.linear_min_potential_net) return 'linear_full_potential_net must be greater than linear_min_potential_net.';
  if (settings.linear_score_allocation_power < 0.5 || settings.linear_score_allocation_power > 5) return 'linear_score_allocation_power must be between 0.5 and 5.0.';
  if (settings.linear_high_bearish_confidence_min_threshold >= settings.linear_high_bearish_confidence_max_threshold) return 'Linear high bearish confidence max threshold must be greater than min threshold.';
  for (const key of ['linear_target_band_tolerance_pct', 'linear_add_band_tolerance_pct', 'linear_trim_band_tolerance_pct']) {
    if (settings[key] < 0 || settings[key] > 100) return `${key} must be between 0 and 100.`;
  }
  if (settings.action_trigger_max_required_upside <= settings.action_trigger_min_required_upside) return 'Trigger max required upside must be greater than trigger min required upside.';
  return null;
}

function cancelGeneralConfigurationEdits() {
  if (!savedGeneralSettings) return;
  configIbPriceWaitSecondsEl.value = savedGeneralSettings.ib_price_wait_seconds ?? 5;
  configIbDelayedPriceExtraWaitSecondsEl.value = savedGeneralSettings.ib_delayed_price_extra_wait_seconds ?? 5;
  configScenarioMultiPassEnabledEl.checked = Boolean(savedGeneralSettings.scenario_multi_pass_enabled);
  configScenarioPassCountEl.value = savedGeneralSettings.scenario_pass_count || 1;
  applyScenarioProbabilitySettingsToForm(savedGeneralSettings.scenario_probability_settings || DEFAULT_SCENARIO_PROBABILITY_SETTINGS);
  applyRatingSettingsToForm(savedGeneralSettings.rating_settings || DEFAULT_RATING_SETTINGS);
  applyActionPlanSettingsToForm(savedGeneralSettings.action_plan_settings || DEFAULT_ACTION_PLAN_SETTINGS);
  configurationStatusEl.textContent = 'Unsaved changes reverted.';
  configurationStatusEl.className = 'status';
}

function restoreDefaultRatingSettings() {
  applyScenarioProbabilitySettingsToForm(DEFAULT_SCENARIO_PROBABILITY_SETTINGS);
  applyRatingSettingsToForm(DEFAULT_RATING_SETTINGS);
  applyActionPlanSettingsToForm(DEFAULT_ACTION_PLAN_SETTINGS);
  configurationStatusEl.textContent = 'Default rating, scenario probability, and Action Plan settings restored in form. Click Save to persist.';
  configurationStatusEl.className = 'status';
}

function applyTwsDataToggleState(useTwsData, message = '') {
  twsDataToggleEl.checked = Boolean(useTwsData);
  twsDataStatusEl.textContent = message;
  twsDataStatusEl.className = message ? 'status' : 'status';
}

async function loadTwsDataToggleState() {
  try {
    const response = await fetch('/api/configuration/general');
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load TWS data switch state'));
    const settings = payload.settings || {};
    applyTwsDataToggleState(Boolean(settings.use_tws_data), settings.use_tws_data ? 'TWS data enabled.' : 'TWS data disabled.');
  } catch (error) {
    applyTwsDataToggleState(false, `Error: ${error.message}`);
    twsDataStatusEl.className = 'status error';
  }
}

async function updateTwsDataToggle(enabled) {
  if (isUpdatingTwsDataToggle) return;
  isUpdatingTwsDataToggle = true;
  twsDataToggleEl.disabled = true;
  twsDataStatusEl.textContent = enabled ? 'Enabling TWS data…' : 'Disabling TWS data…';
  twsDataStatusEl.className = 'status';
  try {
    const response = await fetch('/api/configuration/general', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ settings: { use_tws_data: enabled } }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to update TWS data switch'));
    const effective = Boolean(payload?.settings?.use_tws_data);
    applyTwsDataToggleState(
      effective,
      enabled && !effective
        ? 'TWS unavailable. Data from TWS remains off.'
        : (effective ? 'TWS data enabled.' : 'TWS data disabled.'),
    );
    if (!effective) {
      twsDataStatusEl.className = enabled ? 'status error' : 'status';
    }
  } catch (error) {
    twsDataToggleEl.checked = false;
    twsDataStatusEl.textContent = `Error: ${error.message}`;
    twsDataStatusEl.className = 'status error';
  } finally {
    twsDataToggleEl.disabled = false;
    isUpdatingTwsDataToggle = false;
  }
}

async function loadGeneralConfiguration() {
  configurationStatusEl.textContent = 'Loading configuration…'; configurationStatusEl.className = 'status';
  try { const response = await fetch('/api/configuration/general'); const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to load configuration'));
    const settings = payload.settings || {};
    savedGeneralSettings = settings;
    configIbPriceWaitSecondsEl.value = settings.ib_price_wait_seconds ?? 5;
    configIbDelayedPriceExtraWaitSecondsEl.value = settings.ib_delayed_price_extra_wait_seconds ?? 5;
    configScenarioMultiPassEnabledEl.checked = Boolean(settings.scenario_multi_pass_enabled);
    configScenarioPassCountEl.value = settings.scenario_pass_count || 1;
    applyScenarioProbabilitySettingsToForm(settings.scenario_probability_settings || DEFAULT_SCENARIO_PROBABILITY_SETTINGS);
    applyRatingSettingsToForm(settings.rating_settings || DEFAULT_RATING_SETTINGS);
    applyActionPlanSettingsToForm(settings.action_plan_settings || DEFAULT_ACTION_PLAN_SETTINGS);
    applyTwsDataToggleState(Boolean(settings.use_tws_data), Boolean(settings.use_tws_data) ? 'TWS data enabled.' : 'TWS data disabled.');
    configurationStatusEl.textContent = 'Configuration loaded.';
  } catch (error) { configurationStatusEl.textContent = `Error: ${error.message}`; configurationStatusEl.className = 'status error'; }
}

async function saveGeneralConfiguration() {
  const waitSeconds = Number(configIbPriceWaitSecondsEl.value);
  const delayedPriceExtraWaitSeconds = Number(configIbDelayedPriceExtraWaitSecondsEl.value);
  const passCount = Number(configScenarioPassCountEl.value);
  if (!Number.isFinite(waitSeconds) || waitSeconds < 1 || waitSeconds > 30) {
    configurationStatusEl.textContent = 'Error: Price wait time must be between 1 and 30 seconds.';
    configurationStatusEl.className = 'status error';
    return;
  }
  if (!Number.isFinite(delayedPriceExtraWaitSeconds) || delayedPriceExtraWaitSeconds < 0 || delayedPriceExtraWaitSeconds > 30) {
    configurationStatusEl.textContent = 'Error: Delayed price extra wait time must be between 0 and 30 seconds.';
    configurationStatusEl.className = 'status error';
    return;
  }
  if (!Number.isInteger(passCount) || passCount < 1 || passCount > 10) {
    configurationStatusEl.textContent = 'Error: Scenario pass count must be an integer between 1 and 10.';
    configurationStatusEl.className = 'status error';
    return;
  }

  const scenarioProbabilitySettings = getScenarioProbabilitySettingsFromForm();
  const scenarioProbabilityError = validateScenarioProbabilitySettings(scenarioProbabilitySettings);
  if (scenarioProbabilityError) {
    configurationStatusEl.textContent = `Error: ${scenarioProbabilityError}`;
    configurationStatusEl.className = 'status error';
    return;
  }

  const ratingSettings = getRatingSettingsFromForm();
  const ratingValidationError = validateRatingSettings(ratingSettings);
  if (ratingValidationError) {
    configurationStatusEl.textContent = `Error: ${ratingValidationError}`;
    configurationStatusEl.className = 'status error';
    return;
  }

  const actionPlanSettings = getActionPlanSettingsFromForm();
  const actionPlanValidationError = validateActionPlanSettings(actionPlanSettings);
  if (actionPlanValidationError) {
    configurationStatusEl.textContent = `Error: ${actionPlanValidationError}`;
    configurationStatusEl.className = 'status error';
    return;
  }

  configurationStatusEl.textContent = 'Saving configuration…'; configurationStatusEl.className = 'status';
  try { const response = await fetch('/api/configuration/general', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ settings: { ib_price_wait_seconds: waitSeconds, ib_delayed_price_extra_wait_seconds: delayedPriceExtraWaitSeconds, scenario_multi_pass_enabled: configScenarioMultiPassEnabledEl.checked, scenario_pass_count: passCount, scenario_probability_settings: scenarioProbabilitySettings, rating_settings: ratingSettings, action_plan_settings: actionPlanSettings, use_tws_data: Boolean(twsDataToggleEl.checked) } }) });
    const payload = await response.json(); if (!response.ok) throw new Error(extractErrorMessage(payload, 'Unable to save configuration')); savedGeneralSettings = payload.settings || null; configurationStatusEl.textContent = 'Configuration saved.';
    if (savedGeneralSettings) {
      applyScenarioProbabilitySettingsToForm(savedGeneralSettings.scenario_probability_settings || DEFAULT_SCENARIO_PROBABILITY_SETTINGS);
      applyRatingSettingsToForm(savedGeneralSettings.rating_settings || DEFAULT_RATING_SETTINGS);
      applyActionPlanSettingsToForm(savedGeneralSettings.action_plan_settings || DEFAULT_ACTION_PLAN_SETTINGS);
      applyTwsDataToggleState(Boolean(savedGeneralSettings.use_tws_data), Boolean(savedGeneralSettings.use_tws_data) ? 'TWS data enabled.' : 'TWS data disabled.');
    }
    await loadAnalysis();
  } catch (error) { configurationStatusEl.textContent = `Error: ${error.message}`; configurationStatusEl.className = 'status error'; }
}

positionSortHeaders.forEach((header) => header.addEventListener('click', () => {
  const { sortKey } = header.dataset; if (!sortKey) return;
  if (positionSort.key === sortKey) positionSort.direction = positionSort.direction === 'asc' ? 'desc' : 'asc'; else positionSort = { key: sortKey, direction: 'asc' };
  updateSortHeaderState(); renderPositions();
}));
analysisSortHeaders.forEach((header) => header.addEventListener('click', () => {
  const { sortKey } = header.dataset; if (!sortKey) return;
  if (analysisSort.key === sortKey) analysisSort.direction = analysisSort.direction === 'asc' ? 'desc' : 'asc'; else analysisSort = { key: sortKey, direction: 'asc' };
  updateAnalysisSortHeaderState(); renderAnalysisList();
}));
actionPlanLinearSortHeaders.forEach((header) => header.addEventListener('click', () => {
  const { sortKey } = header.dataset; if (!sortKey) return;
  if (actionPlanLinearSort.key === sortKey) actionPlanLinearSort.direction = actionPlanLinearSort.direction === 'asc' ? 'desc' : 'asc'; else actionPlanLinearSort = { key: sortKey, direction: sortKey === 'linear_allocation_score' ? 'desc' : 'asc' };
  updateActionPlanSortHeaderState(); renderActionPlan();
}));
analysisPortfolioFilterEl.addEventListener('change', () => {
  portfolioFilter = analysisPortfolioFilterEl.value || 'all';
  renderAnalysisList();
});
analysisRatingFilterToggleEl.addEventListener('click', () => {
  const isOpen = analysisRatingFilterEl?.dataset.open === 'true';
  setRatingFilterOpen(!isOpen);
});
positionsRatingFilterToggleEl.addEventListener('click', () => {
  const isOpen = positionsRatingFilterEl?.dataset.open === 'true';
  setPositionsRatingFilterOpen(!isOpen);
});
actionPlanRatingFilterToggleEl.addEventListener('click', () => {
  const isOpen = actionPlanRatingFilterEl?.dataset.open === 'true';
  setActionPlanRatingFilterOpen(!isOpen);
});
actionPlanActionFilterToggleEl.addEventListener('click', () => {
  const isOpen = actionPlanActionFilterEl?.dataset.open === 'true';
  setActionPlanActionFilterOpen(!isOpen);
});
earningsCalendarDateFilterToggleEl.addEventListener('click', () => {
  const isOpen = earningsCalendarDateFilterEl?.dataset.open === 'true';
  setEarningsCalendarDateFilterOpen(!isOpen);
});
earningsCalendarFiscalYearFilterToggleEl.addEventListener('click', () => {
  const isOpen = earningsCalendarFiscalYearFilterEl?.dataset.open === 'true';
  setEarningsCalendarFiscalYearFilterOpen(!isOpen);
});
earningsCalendarFiscalQuarterFilterToggleEl.addEventListener('click', () => {
  const isOpen = earningsCalendarFiscalQuarterFilterEl?.dataset.open === 'true';
  setEarningsCalendarFiscalQuarterFilterOpen(!isOpen);
});
analysisRatingFilterPanelEl.addEventListener('change', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || target.type !== 'checkbox') return;
  const next = getSelectedRatings();
  if (target.checked) next.add(target.value);
  else next.delete(target.value);
  setSelectedRatings(next);
  renderAnalysisList();
});
positionsRatingFilterPanelEl.addEventListener('change', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || target.type !== 'checkbox') return;
  const next = getSelectedPositionRatings();
  if (target.checked) next.add(target.value);
  else next.delete(target.value);
  setSelectedPositionRatings(next);
  renderPositions();
});
actionPlanRatingFilterPanelEl.addEventListener('change', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || target.type !== 'checkbox') return;
  const next = getSelectedActionPlanRatings();
  if (target.checked) next.add(target.value);
  else next.delete(target.value);
  setSelectedActionPlanRatings(next);
  renderActionPlan();
});
actionPlanActionFilterPanelEl.addEventListener('change', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || target.type !== 'checkbox') return;
  const next = getSelectedActionPlanActions();
  if (target.checked) next.add(target.value);
  else next.delete(target.value);
  setSelectedActionPlanActions(next);
  renderActionPlan();
});
earningsCalendarDateFilterPanelEl.addEventListener('change', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || target.type !== 'checkbox') return;
  const next = getSelectedEarningsCalendarDateFilters();
  if (target.checked) next.add(target.value);
  else next.delete(target.value);
  setSelectedEarningsCalendarDateFilters(next);
  renderEarningsCalendarTable();
});
earningsCalendarFiscalYearFilterPanelEl.addEventListener('change', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || target.type !== 'checkbox') return;
  const next = getSelectedEarningsCalendarFiscalYears();
  if (target.checked) next.add(target.value);
  else next.delete(target.value);
  setSelectedEarningsCalendarFiscalYears(next);
  renderEarningsCalendarTable();
});
earningsCalendarFiscalQuarterFilterPanelEl.addEventListener('change', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || target.type !== 'checkbox') return;
  const next = getSelectedEarningsCalendarFiscalQuarters();
  if (target.checked) next.add(target.value);
  else next.delete(target.value);
  setSelectedEarningsCalendarFiscalQuarters(next);
  renderEarningsCalendarTable();
});
analysisRatingFilterSelectAllEl.addEventListener('click', () => {
  setSelectedRatings(getAllRatingFilterKeys());
  renderAnalysisList();
});
positionsRatingFilterSelectAllEl.addEventListener('click', () => {
  setSelectedPositionRatings(getAllRatingFilterKeys());
  renderPositions();
});
actionPlanRatingFilterSelectAllEl.addEventListener('click', () => {
  setSelectedActionPlanRatings(getAllRatingFilterKeys());
  renderActionPlan();
});
actionPlanActionFilterSelectAllEl.addEventListener('click', () => {
  setSelectedActionPlanActions(getAllActionPlanActionFilterKeys());
  renderActionPlan();
});
earningsCalendarDateFilterSelectAllEl.addEventListener('click', () => {
  setSelectedEarningsCalendarDateFilters(getAllEarningsCalendarDateFilterKeys());
  renderEarningsCalendarTable();
});
earningsCalendarFiscalYearFilterSelectAllEl.addEventListener('click', () => {
  setSelectedEarningsCalendarFiscalYears(getAllEarningsCalendarFiscalYearKeys());
  renderEarningsCalendarTable();
});
earningsCalendarFiscalQuarterFilterSelectAllEl.addEventListener('click', () => {
  setSelectedEarningsCalendarFiscalQuarters(getAllEarningsCalendarFiscalQuarterKeys());
  renderEarningsCalendarTable();
});
analysisRatingFilterClearEl.addEventListener('click', () => {
  setSelectedRatings(new Set());
  renderAnalysisList();
});
positionsRatingFilterClearEl.addEventListener('click', () => {
  setSelectedPositionRatings(new Set());
  renderPositions();
});
actionPlanRatingFilterClearEl.addEventListener('click', () => {
  setSelectedActionPlanRatings(new Set());
  renderActionPlan();
});
actionPlanActionFilterClearEl.addEventListener('click', () => {
  setSelectedActionPlanActions(new Set());
  renderActionPlan();
});
earningsCalendarDateFilterClearEl.addEventListener('click', () => {
  setSelectedEarningsCalendarDateFilters(new Set());
  renderEarningsCalendarTable();
});
earningsCalendarFiscalYearFilterClearEl.addEventListener('click', () => {
  setSelectedEarningsCalendarFiscalYears(new Set());
  renderEarningsCalendarTable();
});
earningsCalendarFiscalQuarterFilterClearEl.addEventListener('click', () => {
  setSelectedEarningsCalendarFiscalQuarters(new Set());
  renderEarningsCalendarTable();
});
document.addEventListener('click', (event) => {
  if (!(event.target instanceof Node)) return;
  if (analysisRatingFilterEl && !analysisRatingFilterEl.contains(event.target)) setRatingFilterOpen(false);
  if (positionsRatingFilterEl && !positionsRatingFilterEl.contains(event.target)) setPositionsRatingFilterOpen(false);
  if (actionPlanRatingFilterEl && !actionPlanRatingFilterEl.contains(event.target)) setActionPlanRatingFilterOpen(false);
  if (actionPlanActionFilterEl && !actionPlanActionFilterEl.contains(event.target)) setActionPlanActionFilterOpen(false);
  if (earningsCalendarDateFilterEl && !earningsCalendarDateFilterEl.contains(event.target)) setEarningsCalendarDateFilterOpen(false);
  if (earningsCalendarFiscalYearFilterEl && !earningsCalendarFiscalYearFilterEl.contains(event.target)) setEarningsCalendarFiscalYearFilterOpen(false);
  if (earningsCalendarFiscalQuarterFilterEl && !earningsCalendarFiscalQuarterFilterEl.contains(event.target)) setEarningsCalendarFiscalQuarterFilterOpen(false);
});
window.addEventListener('resize', repositionOpenFloatingFilters);
window.addEventListener('scroll', repositionOpenFloatingFilters, true);
document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  setRatingFilterOpen(false);
  setPositionsRatingFilterOpen(false);
  setActionPlanRatingFilterOpen(false);
  setActionPlanActionFilterOpen(false);
  setEarningsCalendarDateFilterOpen(false);
  setEarningsCalendarFiscalYearFilterOpen(false);
  setEarningsCalendarFiscalQuarterFilterOpen(false);
  closeConfigHelpModal();
  closeLinearCapExplanationModal();
});
configHelpCloseBtn?.addEventListener('click', closeConfigHelpModal);
configHelpModalEl?.addEventListener('click', (event) => {
  if (event.target === configHelpModalEl) closeConfigHelpModal();
});
linearCapExplanationCloseBtn?.addEventListener('click', closeLinearCapExplanationModal);
linearCapExplanationModalEl?.addEventListener('click', (event) => {
  if (event.target === linearCapExplanationModalEl) closeLinearCapExplanationModal();
});
analysisSelectAllEl.addEventListener('change', () => {
  const visibleItems = getFilteredAnalysisItems();
  if (analysisSelectAllEl.checked) visibleItems.forEach((item) => selectedAnalysisSymbols.add(item.symbol));
  else visibleItems.forEach((item) => selectedAnalysisSymbols.delete(item.symbol));
  renderAnalysisList();
});

refreshBtn.addEventListener('click', () => loadPositions({ refresh: true }));
analysisAddBtn.addEventListener('click', addAnalysisSymbol);
analysisImportBtn.addEventListener('click', importAnalysisFromPositions);
analysisRefreshPricesBtn.addEventListener('click', refreshAnalysisPrices);
analysisUpdateMomentumBtn.addEventListener('click', updateAnalysisMomentum);
analysisRerunSelectedBtn.addEventListener('click', rerunSelectedSymbolsScenarios);
analysisCheckEventsBtn.addEventListener('click', checkRecentEventsForSelected);
analysisSymbolInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') addAnalysisSymbol(); });
analysisBackBtn.addEventListener('click', () => {
  if (analysisDetailOrigin === 'positions') {
    setView('positions');
    return;
  }
  if (analysisDetailOrigin === 'action_plan') {
    setView('action-plan', { skipLoad: true });
    return;
  }
  if (analysisDetailOrigin === 'earnings_review') {
    setView('earnings-review', { skipLoad: true });
    return;
  }
  showAnalysisList();
});
alertDetailBackBtn.addEventListener('click', backToAlertsFromDetail);
alertDetailReviewBtn.addEventListener('click', () => { if (currentAlertDetailId) updateAlertStatus(currentAlertDetailId, 'Reviewed', { stayOnDetail: true, advanceAfterUpdate: true }); });
alertDetailDismissBtn.addEventListener('click', () => { if (currentAlertDetailId) updateAlertStatus(currentAlertDetailId, 'Dismissed', { stayOnDetail: true, advanceAfterUpdate: true }); });
alertDetailPrevBtn.addEventListener('click', () => openPreviousAlertDetail());
alertDetailNextBtn.addEventListener('click', () => openNextAlertDetail());
alertDetailEditVarsBtn.addEventListener('click', () => {
  if (!alertDetailAnalysisState?.version) return;
  alertDetailIsEditingVariables = true;
  renderAlertDetailVariablesTable();
});
alertDetailAddVarBtn.addEventListener('click', () => {
  const row = document.createElement('tr');
  row.innerHTML = '<td><input class="alert-var-text" type="text" value=""></td><td><select class="alert-var-type"><option value="Bullish">Bullish</option><option value="Bearish">Bearish</option></select></td><td><select class="alert-var-driver-category"><option value="Core Driver" selected>Core Driver</option><option value="Potential Driver">Potential Driver</option></select></td><td><input class="alert-var-confidence" type="number" min="0" max="10" step="1" value="5"></td><td><input class="alert-var-importance" type="number" min="0" max="10" step="1" value="5"></td><td><button class="alert-var-delete-btn">Delete</button></td>';
  alertDetailVarsBody.appendChild(row);
  row.querySelector('.alert-var-delete-btn')?.addEventListener('click', () => row.remove());
});
alertDetailSaveVarsBtn.addEventListener('click', saveAlertDetailVariables);
alertDetailOpenAnalysisBtn.addEventListener('click', () => {
  if (!currentAlertDetailSymbol) return;
  openAnalysisDetailForSymbol(currentAlertDetailSymbol, { origin: 'analysis' });
});
alertDetailCancelVarsBtn.addEventListener('click', () => {
  alertDetailIsEditingVariables = false;
  renderAlertDetailVariablesTable();
  alertDetailKeyvarsStatusEl.textContent = 'Key variable editing canceled.';
  alertDetailKeyvarsStatusEl.className = 'status';
});
alertDetailRerunBtn.addEventListener('click', rerunAlertDetailScenarios);
alertsStatusFilterEl.addEventListener('change', () => {
  alertsStatusFilter = alertsStatusFilterEl.value || 'New';
  renderAlertsList();
  alertsStatusEl.textContent = `Showing ${getFilteredAlerts().length} of ${latestAlerts.length} alert(s).`;
});
analysisScenarioInfoBtn.addEventListener('click', () => analysisScenarioInfoModal.classList.remove('hidden'));
analysisScenarioInfoCloseBtn.addEventListener('click', () => analysisScenarioInfoModal.classList.add('hidden'));
analysisScenarioOverlayTabButtons.forEach((button) => {
  button.addEventListener('click', () => setScenarioOverlayTab(button.dataset.scenarioTab));
});
analysisAddExternalScenarioBtn.addEventListener('click', () => openExternalScenarioModal());
analysisExternalScenarioTemplateBtn.addEventListener('click', () => {
  analysisExternalScenarioJsonEl.value = getExternalScenarioTemplate();
});
analysisExternalScenarioSaveBtn.addEventListener('click', saveExternalScenarioFromModal);
analysisExternalScenarioCancelBtn.addEventListener('click', closeExternalScenarioModal);
analysisExternalScenarioCancelFormBtn.addEventListener('click', closeExternalScenarioModal);
analysisFinalScenarioPanelEl.addEventListener('click', (event) => {
  const target = event.target;
  if (target instanceof HTMLElement && target.classList.contains('final-scenario-recalculate-btn')) recalculateFinalScenario();
});
analysisExternalScenariosPanelEl.addEventListener('click', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (target.id === 'analysis-external-add-another-btn') {
    openExternalScenarioModal();
    return;
  }
  if (target.id === 'analysis-external-recalculate-btn') {
    recalculateFinalScenario();
    return;
  }
  const editId = target.dataset.externalId;
  if (target.classList.contains('external-scenario-edit-btn') && editId) {
    const item = getCurrentExternalScenarios().find((scenario) => Number(scenario.id) === Number(editId));
    if (item) openExternalScenarioModal(item);
    return;
  }
  if (target.classList.contains('external-scenario-remove-btn') && editId) {
    removeExternalScenario(editId);
  }
});

analysisSummary.addEventListener('click', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const releaseNav = target.dataset.releaseNav;
  if (releaseNav && analysisDetailState) {
    const history = analysisDetailState.release_history || [];
    const currentIndex = Number.isInteger(analysisDetailState.selected_release_index) ? analysisDetailState.selected_release_index : 0;
    if (releaseNav === 'up') analysisDetailState.selected_release_index = Math.max(0, currentIndex - 1);
    if (releaseNav === 'down') analysisDetailState.selected_release_index = Math.min(history.length - 1, currentIndex + 1);
    renderAnalysisDetail();
    return;
  }
  if (target.id === 'analysis-business-model-edit-btn') {
    isEditingBusinessModel = true;
    renderAnalysisDetail();
    return;
  }
  if (target.id === 'analysis-business-model-save-btn') {
    saveEditedBusinessModel();
    return;
  }
  if (target.id === 'analysis-business-model-cancel-btn') {
    cancelEditedBusinessModel();
    return;
  }
  if (target.id === 'analysis-business-summary-edit-btn') {
    isEditingBusinessSummary = true;
    renderAnalysisDetail();
    return;
  }
  if (target.id === 'analysis-business-summary-save-btn') {
    saveEditedBusinessSummary();
    return;
  }
  if (target.id === 'analysis-business-summary-cancel-btn') {
    cancelEditedBusinessSummary();
    return;
  }
});
analysisSummary.addEventListener('change', (event) => {
  const target = event.target;
  if (target.id === 'analysis-frontier-score-select') {
    saveFrontierScore(target.value);
  }
});
analysisVariableTabButtons.forEach((button) => {
  button.addEventListener('click', () => {
    if (isEditingVariables) syncActiveAnalysisVariableRowsFromDom();
    activeAnalysisVariableCategory = normalizeDriverCategory(button.dataset.driverCategory);
    renderVariablesTable();
  });
});
analysisCopyKeyVarsBtn.addEventListener('click', copyAnalysisKeyVariablesJson);
analysisCopyReviewPromptBtn.addEventListener('click', copyAnalysisReviewPrompt);
analysisEditVariablesBtn.addEventListener('click', () => {
  editableAnalysisVariables = getCurrentAnalysisKeyVariables().map(normalizeAnalysisVariableForUi);
  isEditingVariables = true;
  renderVariablesTable();
});
analysisImportVariablesBtn.addEventListener('click', openKeyVariableImportModal);
analysisKeyVariableImportTemplateBtn.addEventListener('click', () => {
  analysisKeyVariableImportJsonEl.value = getKeyVariableImportTemplate();
});
analysisKeyVariableImportSaveBtn.addEventListener('click', importKeyVariablesFromJson);
analysisKeyVariableImportCloseBtn.addEventListener('click', closeKeyVariableImportModal);
analysisKeyVariableImportCancelBtn.addEventListener('click', closeKeyVariableImportModal);
analysisAddVariableBtn.addEventListener('click', () => {
  if (!isEditingVariables) return;
  syncActiveAnalysisVariableRowsFromDom();
  const draft = getAnalysisVariableEditDraft();
  const newIndex = draft.push({
    variable_text: '',
    variable_type: 'Bullish',
    driver_category: normalizeDriverCategory(activeAnalysisVariableCategory),
    confidence: 5,
    importance: 5,
  }) - 1;
  renderVariablesTable();
  const newRow = analysisVariablesBody.querySelector(`tr[data-variable-index="${newIndex}"]`);
  newRow?.querySelector('.var-text')?.focus();
});
analysisCancelVariablesBtn.addEventListener('click', () => {
  isEditingVariables = false;
  editableAnalysisVariables = null;
  renderVariablesTable();
});
analysisSaveVariablesBtn.addEventListener('click', saveEditedVariables);
analysisRerunBtn.addEventListener('click', rerunScenarios);
analysisVersionPrevBtn.addEventListener('click', () => {
  const idx = selectedVersionIndex(); const prev = analysisDetailState.versions[idx - 1]; if (prev) loadAnalysisDetail(analysisDetailState.symbol, prev.id);
});
analysisVersionNextBtn.addEventListener('click', () => {
  const idx = selectedVersionIndex(); const next = analysisDetailState.versions[idx + 1]; if (next) loadAnalysisDetail(analysisDetailState.symbol, next.id);
});
analysisVersionSelect.addEventListener('change', () => loadAnalysisDetail(analysisDetailState.symbol, analysisVersionSelect.value));

promptSaveBtn.addEventListener('click', savePromptConfiguration);
promptResetBtn.addEventListener('click', resetPromptConfiguration);
promptPreviewBtn.addEventListener('click', previewPromptConfiguration);
promptPreviewSymbolInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') previewPromptConfiguration(); });
earningsReviewGenerateBtn.addEventListener('click', generateEarningsWatchpoints);
earningsReviewAnalyseBtn.addEventListener('click', analyseEarningsWatchpoints);
earningsReviewBackBtn.addEventListener('click', async () => {
  if (earningsReviewSelectedSymbol) {
    await openEarningsReviewSymbolHistory(earningsReviewSelectedSymbol);
  } else {
    await loadEarningsReview();
  }
});
earningsReviewSymbolBackBtn.addEventListener('click', async () => {
  await loadEarningsReview();
});
earningsReviewAddBtn.addEventListener('click', addEarningsReviewSymbol);
earningsReviewTabWorkflowBtn.addEventListener('click', async () => {
  setEarningsReviewTab('workflow');
  await loadEarningsReview();
});
earningsReviewTabCalendarBtn.addEventListener('click', async () => {
  setEarningsReviewTab('calendar');
  await loadEarningsReview();
});
earningsCalendarPortfolioFilterEl.addEventListener('change', () => {
  earningsCalendarPortfolioFilter = earningsCalendarPortfolioFilterEl.value || 'all';
  renderEarningsCalendarTable();
});
earningsCalendarAddBtn.addEventListener('click', createEarningsCalendarEntry);
[earningsCalendarAddSymbolEl, earningsCalendarAddFiscalYearEl, earningsCalendarAddReleaseDateEl].forEach((input) => {
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') createEarningsCalendarEntry();
  });
});
earningsCalendarReleaseDateHeaderEl.addEventListener('click', () => {
  earningsCalendarReleaseDateSortDirection = earningsCalendarReleaseDateSortDirection === 'asc' ? 'desc' : 'asc';
  renderEarningsCalendarTable();
});
earningsReviewAddSymbolEl.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    addEarningsReviewSymbol();
  }
});
earningsReviewCreateBtn.addEventListener('click', () => toggleEarningsReviewCreateForm(true));
earningsReviewCreateCancelBtn.addEventListener('click', () => toggleEarningsReviewCreateForm(false));
earningsReviewCreateSubmitBtn.addEventListener('click', createEarningsReviewRecord);
earningsReviewDocumentChooseBtn.addEventListener('click', () => earningsReviewDocumentFileEl.click());
earningsReviewDocumentFileEl.addEventListener('change', () => {
  const file = earningsReviewDocumentFileEl.files && earningsReviewDocumentFileEl.files[0];
  earningsReviewDocumentFileNameEl.textContent = file?.name || 'No file chosen';
});
earningsReviewDocumentUploadBtn.addEventListener('click', uploadEarningsReviewDocument);
configSaveBtn.addEventListener('click', saveGeneralConfiguration);
configCancelBtn.addEventListener('click', cancelGeneralConfigurationEdits);
configRestoreDefaultsBtn.addEventListener('click', restoreDefaultRatingSettings);
actionPlanRefreshBtn.addEventListener('click', loadActionPlan);
actionPlanDetailBackBtn.addEventListener('click', showActionPlanList);
actionPlanOpenAnalysisBtn.addEventListener('click', () => {
  if (!selectedActionPlanDetail?.symbol) return;
  openAnalysisDetailForSymbol(selectedActionPlanDetail.symbol, { origin: 'action_plan' });
});
configActionPlanInputs.forEach((input) => input.addEventListener('input', updateActionPlanBucketTotal));
twsDataToggleEl.addEventListener('change', () => updateTwsDataToggle(Boolean(twsDataToggleEl.checked)));
backupExportBtn.addEventListener('click', exportBackupFile);
backupImportBtn.addEventListener('click', restoreBackupFile);

updateSortHeaderState();
updateAnalysisSortHeaderState();
updateActionPlanSortHeaderState();
setSelectedRatings(getAllRatingFilterKeys());
setRatingFilterOpen(false);
setSelectedPositionRatings(getAllRatingFilterKeys());
setSelectedActionPlanRatings(getAllRatingFilterKeys());
setSelectedActionPlanActions(getAllActionPlanActionFilterKeys());
setSelectedEarningsCalendarDateFilters(new Set());
setEarningsReviewTab('calendar');
setPositionsRatingFilterOpen(false);
setActionPlanRatingFilterOpen(false);
setActionPlanActionFilterOpen(false);
setEarningsCalendarDateFilterOpen(false);
initializeConfigHelpIcons();
loadTwsDataToggleState();

setView('analysis');
