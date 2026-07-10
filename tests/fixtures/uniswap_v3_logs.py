"""Synthetic ABI-encoded Uniswap V3 logs for unit testing (Story 1B.1).

Values are realistic but not from real mainnet transactions.
Pool: USDC/WETH 0.05% — 0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640
token0: USDC  0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
token1: WETH  0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2
"""

from eth_abi import encode as abi_encode

POOL_ADDRESS = "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"
TOKEN0 = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # USDC
TOKEN1 = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"  # WETH
BLOCK_TS = 1698148811  # 2023-10-24T12:00:11Z

SWAP_TOPIC = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
MINT_TOPIC = "0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde"
BURN_TOPIC = "0x0c396cd989a39f4459b5fa1aed6a9a8dcdbc45908acfd67e028cd568da98982c"
SENDER = "0x" + "aa" * 20
RECIPIENT = "0x" + "bb" * 20
OWNER = "0x" + "cc" * 20
TX_HASH = "0x" + "ab" * 32


def _b(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str.removeprefix("0x"))


def _addr_topic(addr: str) -> bytes:
    """Pad a 20-byte address into a 32-byte indexed topic."""
    return bytes(12) + _b(addr)


# Log 1: Swap — amount0=-1000000000 USDC (negative), amount1=+500000000000000000 WETH
SWAP_LOG_1 = {
    "address": POOL_ADDRESS,
    "topics": [_b(SWAP_TOPIC), _addr_topic(SENDER), _addr_topic(RECIPIENT)],
    "data": abi_encode(
        ["int256", "int256", "uint160", "uint128", "int24"],
        [-1000000000, 500000000000000000, 2**80, 10**18, 0],
    ),
    "blockNumber": 18500000,
    "transactionHash": _b(TX_HASH),
    "logIndex": 42,
}

# Log 2: Swap — amount0 positive, amount1 negative (reverse direction)
SWAP_LOG_2 = {
    "address": POOL_ADDRESS,
    "topics": [_b(SWAP_TOPIC), _addr_topic(SENDER), _addr_topic(RECIPIENT)],
    "data": abi_encode(
        ["int256", "int256", "uint160", "uint128", "int24"],
        [2000000000, -999000000000000000, 2**79, 10**18, -100],
    ),
    "blockNumber": 18500001,
    "transactionHash": _b(TX_HASH),
    "logIndex": 7,
}

# Log 3: Mint — add liquidity, amount0=5000000 USDC, amount1=2500000000000000000 WETH
MINT_LOG_1 = {
    "address": POOL_ADDRESS,
    "topics": [
        _b(MINT_TOPIC),
        _addr_topic(OWNER),
        (-887272).to_bytes(32, "big", signed=True),
        (887272).to_bytes(32, "big"),
    ],
    "data": abi_encode(
        ["address", "uint128", "uint256", "uint256"],
        [SENDER, 10**15, 5000000, 2500000000000000000],
    ),
    "blockNumber": 18500002,
    "transactionHash": _b(TX_HASH),
    "logIndex": 1,
}

# Log 4: Burn — remove liquidity
BURN_LOG_1 = {
    "address": POOL_ADDRESS,
    "topics": [
        _b(BURN_TOPIC),
        _addr_topic(OWNER),
        (-887272).to_bytes(32, "big", signed=True),
        (887272).to_bytes(32, "big"),
    ],
    "data": abi_encode(
        ["uint128", "uint256", "uint256"],
        [5 * 10**14, 2500000, 1250000000000000000],
    ),
    "blockNumber": 18500003,
    "transactionHash": _b(TX_HASH),
    "logIndex": 3,
}

# Log 5: Swap with zero amount1 (edge case)
SWAP_LOG_ZERO = {
    "address": POOL_ADDRESS,
    "topics": [_b(SWAP_TOPIC), _addr_topic(SENDER), _addr_topic(RECIPIENT)],
    "data": abi_encode(
        ["int256", "int256", "uint160", "uint128", "int24"],
        [1, 0, 2**80, 10**18, 0],
    ),
    "blockNumber": 18500004,
    "transactionHash": _b(TX_HASH),
    "logIndex": 0,
}
