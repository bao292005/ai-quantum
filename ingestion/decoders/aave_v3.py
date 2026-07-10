"""Aave V3 event decoder (Story 1B.2).

Converts a raw ``Supply``/``Borrow``/``Withdraw``/``LiquidationCall`` log from the
Aave V3 Pool into a :class:`TickDataEvent` (defined in 1B.1). Unlike Uniswap,
Aave carries the asset addresses in the indexed topics, so ``token0``/``token1``
come from the log itself (``pool_meta`` is accepted for a uniform decoder
interface but unused). Single-asset events set ``token1``/``amount1`` to zero.
"""

from __future__ import annotations

from eth_abi import decode as abi_decode

from ingestion.decoders.uniswap_v3 import (
    PoolMeta,
    TickDataEvent,
    _addr,
    _to_data_bytes,
    _to_int,
    _topic_hex,
    _ts_to_iso,
    _tx_hash,
)

# Real mainnet topic0s. BORROW uses the uint8 interestRateMode signature
# (Borrow(address,address,address,uint256,uint8,uint256,uint16)).
SUPPLY_TOPIC = "0x2b627736bca15cd5381dcf80b0bf11fd197d01a037c52b927a881a10fb73ba61"
BORROW_TOPIC = "0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0"
WITHDRAW_TOPIC = "0x3115d1449a7b732c986cba18244e897a450f61e1bb8d589cd2e69e6c8924f9f7"
LIQUIDATION_TOPIC = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

_SUPPLY_TYPES = ["address", "uint256"]  # user, amount
_BORROW_TYPES = ["address", "uint256", "uint256", "uint256"]  # user, amount, rateMode, borrowRate
_WITHDRAW_TYPES = ["uint256"]  # amount
_LIQUIDATION_TYPES = ["uint256", "uint256", "address", "bool"]  # debtToCover, collateralAmt, liquidator, receiveAToken


def _topic_to_addr(topic) -> str:
    """Extract a lowercase 0x-prefixed address from a 32-byte indexed topic."""
    b = topic if isinstance(topic, (bytes, bytearray)) else bytes.fromhex(str(topic).removeprefix("0x"))
    return "0x" + bytes(b)[-20:].hex()


class AaveV3Decoder:
    """Stateless decoder for Aave V3 Supply/Borrow/Withdraw/LiquidationCall logs."""

    def decode(self, log: dict, pool_meta: PoolMeta, block_timestamp: int) -> TickDataEvent:
        topics = log["topics"]
        topic0 = _topic_hex(topics[0])
        data = _to_data_bytes(log["data"])

        if topic0 == SUPPLY_TOPIC:
            decoded = abi_decode(_SUPPLY_TYPES, data)
            amount0, amount1 = int(decoded[1]), 0
            token0, token1 = _topic_to_addr(topics[1]), ZERO_ADDRESS
            event_type = "supply"
        elif topic0 == BORROW_TOPIC:
            decoded = abi_decode(_BORROW_TYPES, data)
            amount0, amount1 = int(decoded[1]), 0
            token0, token1 = _topic_to_addr(topics[1]), ZERO_ADDRESS
            event_type = "borrow"
        elif topic0 == WITHDRAW_TOPIC:
            decoded = abi_decode(_WITHDRAW_TYPES, data)
            amount0, amount1 = int(decoded[0]), 0
            token0, token1 = _topic_to_addr(topics[1]), ZERO_ADDRESS
            event_type = "withdraw"
        elif topic0 == LIQUIDATION_TOPIC:
            decoded = abi_decode(_LIQUIDATION_TYPES, data)
            amount0, amount1 = int(decoded[1]), int(decoded[0])  # collateralAmt, debtToCover
            token0, token1 = _topic_to_addr(topics[1]), _topic_to_addr(topics[2])
            event_type = "liquidation"
        else:
            raise ValueError(f"Unknown Aave V3 topic: {topic0}")

        return TickDataEvent(
            block_number=_to_int(log["blockNumber"]),
            block_timestamp=_ts_to_iso(block_timestamp),
            protocol="aave_v3",
            event_type=event_type,
            pool_address=_addr(log["address"]),
            token0=token0,
            token1=token1,
            amount0=str(amount0),
            amount1=str(amount1),
            tx_hash=_tx_hash(log["transactionHash"]),
            log_index=_to_int(log["logIndex"]),
        )
