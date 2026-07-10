"""Synthetic ABI-encoded Aave V3 logs for unit testing (Story 1B.2).

Aave V3 Pool: 0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2 (mainnet).
BORROW_TOPIC is the real mainnet topic0 (interestRateMode encoded as uint8 in the
event signature) — confirmed via keccak of
``Borrow(address,address,address,uint256,uint8,uint256,uint16)``.
"""

from eth_abi import encode as abi_encode

AAVE_V3_POOL = "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
WBTC = "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"
USER1 = "0x" + "aa" * 20
USER2 = "0x" + "bb" * 20
TX_HASH = "0x" + "cd" * 32
BLOCK_TS = 1698148811  # 2023-10-24T12:00:11Z

SUPPLY_TOPIC = "0x2b627736bca15cd5381dcf80b0bf11fd197d01a037c52b927a881a10fb73ba61"
BORROW_TOPIC = "0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0"
WITHDRAW_TOPIC = "0x3115d1449a7b732c986cba18244e897a450f61e1bb8d589cd2e69e6c8924f9f7"
LIQUIDATION_TOPIC = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"


def _b(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str.removeprefix("0x"))


def _addr_topic(addr: str) -> bytes:
    """Pad a 20-byte address into a 32-byte indexed topic."""
    return bytes(12) + _b(addr)


# Log 1: Supply — 1000 USDC
SUPPLY_LOG = {
    "address": AAVE_V3_POOL,
    "topics": [_b(SUPPLY_TOPIC), _addr_topic(USDC), _addr_topic(USER2), (0).to_bytes(32, "big")],
    "data": abi_encode(["address", "uint256"], [USER1, 1_000_000_000]),
    "blockNumber": 19000000,
    "transactionHash": _b(TX_HASH),
    "logIndex": 10,
}

# Log 2: Borrow — 0.5 WETH variable rate
BORROW_LOG = {
    "address": AAVE_V3_POOL,
    "topics": [_b(BORROW_TOPIC), _addr_topic(WETH), _addr_topic(USER2), (0).to_bytes(32, "big")],
    "data": abi_encode(
        ["address", "uint256", "uint256", "uint256"],
        [USER1, 500_000_000_000_000_000, 2, 50_000_000_000_000_000],
    ),
    "blockNumber": 19000001,
    "transactionHash": _b(TX_HASH),
    "logIndex": 5,
}

# Log 3: Withdraw — 500 USDC
WITHDRAW_LOG = {
    "address": AAVE_V3_POOL,
    "topics": [_b(WITHDRAW_TOPIC), _addr_topic(USDC), _addr_topic(USER1), _addr_topic(USER2)],
    "data": abi_encode(["uint256"], [500_000_000]),
    "blockNumber": 19000002,
    "transactionHash": _b(TX_HASH),
    "logIndex": 3,
}

# Log 4: LiquidationCall — WBTC collateral, USDC debt
LIQUIDATION_LOG = {
    "address": AAVE_V3_POOL,
    "topics": [_b(LIQUIDATION_TOPIC), _addr_topic(WBTC), _addr_topic(USDC), _addr_topic(USER1)],
    "data": abi_encode(
        ["uint256", "uint256", "address", "bool"],
        [5_000_000_000, 100_000_000, USER2, False],  # debtToCover, liquidatedCollateralAmount
    ),
    "blockNumber": 19000003,
    "transactionHash": _b(TX_HASH),
    "logIndex": 0,
}
