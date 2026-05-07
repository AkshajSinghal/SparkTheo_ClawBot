#!/usr/bin/env python3
from fastapi import FastAPI, BackgroundTasks
import time
from web3 import Web3
import os

BASE_RPC_URL = "https://mainnet.base.org"
WALLET_ADDRESS = "0x7aa4E2f9F661f43CC0639A59B6a1942C9C5396d1"
USDC_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

USDC_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    }
]

app = FastAPI()

# Web3 setup
w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))
if not w3.is_connected():
    raise RuntimeError("Failed to connect to Base Mainnet")

usdc_contract = w3.eth.contract(address=USDC_CONTRACT, abi=USDC_ABI)
wallet_checksum = Web3.to_checksum_address(WALLET_ADDRESS)

LAST_BLOCK_FILE = "/tmp/.x402_last_block"


def get_last_block():
    try:
        with open(LAST_BLOCK_FILE, 'r') as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return "latest"


def save_last_block(block_number):
    with open(LAST_BLOCK_FILE, 'w') as f:
        f.write(str(block_number))


def monitor_loop():
    last_block = get_last_block()
    current_block = w3.eth.block_number
    if last_block == "latest" or current_block <= last_block:
        return
    transfer_filter = usdc_contract.events.Transfer.create_filter(
        fromBlock=last_block + 1,
        toBlock="latest",
        argument_filters={"to": wallet_checksum}
    )
    events = transfer_filter.get_all_events()
    if events:
        for event in events:
            tx_hash = event.transactionHash.hex()
            from_address = event.args['from']
            amount = event.args['value'] / 10**6
            print(f"[PAYMENT] {amount} USDC from {from_address} tx {tx_hash}")
        save_last_block(current_block)
    else:
        save_last_block(current_block)


@app.on_event("startup")
async def startup_event():
    print("x402 FastAPI worker starting up...")
    # Create initial last block file if missing
    if not os.path.exists(LAST_BLOCK_FILE):
        save_last_block("latest")


@app.get("/")
async def root():
    return {"service": "Spark Technical Auditor", "status": "monitoring"}


@app.get("/monitor")
async def monitor(background_tasks: BackgroundTasks):
    """Trigger a one‑off payment check.
    Returns immediately; processing occurs in background.
    """
    background_tasks.add_task(monitor_loop)
    return {"message": "Monitoring task started"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
