# Constants

::: pyraksamp.Keys

## Reliability flags

| Constant | Description |
|---|---|
| `pyraksamp.UNRELIABLE` | No delivery guarantee, no ordering |
| `pyraksamp.UNRELIABLE_SEQUENCED` | No delivery guarantee, newer packets discard older ones |
| `pyraksamp.RELIABLE` | Guaranteed delivery, unordered |
| `pyraksamp.RELIABLE_ORDERED` | Guaranteed delivery, ordered per channel |
| `pyraksamp.RELIABLE_SEQUENCED` | Guaranteed delivery of latest packet only |

## RPC IDs

The `RPC_*` constants mirror the SA:MP 0.3.7 RPC numbering.
For the full list, refer to external SA:MP protocol documentation.
