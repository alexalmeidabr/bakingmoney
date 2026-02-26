import asyncio
import os

from dotenv import load_dotenv

# --- IMPORTANT WINDOWS FIX: must run BEFORE importing ib_insync ---
if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Create and set an event loop explicitly (extra-safe on new Python versions)
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from ib_insync import IB

load_dotenv()

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "7496"))
IB_CLIENT_ID = int(os.getenv("IB_CLIENT_ID", "7"))

ib = IB()
ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)

print("Connected:", ib.isConnected())

summary = ib.accountSummary()
for item in summary:
    if item.tag == "NetLiquidation":
        print("\nTotal Portfolio Value:", item.value, item.currency)

positions = ib.positions()
print("\nYour Holdings:")
for p in positions:
    c = p.contract
    print(f"{c.symbol} | Qty: {p.position} | AvgCost: {p.avgCost}")

ib.disconnect()
