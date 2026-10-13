# API documentation verification — 2026-09-16

This is a review of current official documentation, distinct from successful live execution or guaranteed public archive service. Frozen metadata records the historical collection. [Machine-readable profiles](../metadata/acquisition_profiles.json) bind it to code, chain IDs, deployment/cutoff ranges, pagination and failure handling.

| Service | Documentation checked | Findings used here |
|---|---|---|
| Ethereum | [JSON-RPC](https://ethereum.org/developers/docs/apis/json-rpc/) | `eth_getLogs` uses addresses, topics and block bounds; headers, receipts, calls and code have distinct evidence roles |
| Polygon | [RPC endpoints](https://docs.polygon.technology/pos/reference/rpc-endpoints) | Mainnet chain ID 137; public endpoints include dRPC and Tenderly; public services can restrict traffic |
| Etherscan | [V2 introduction](https://docs.etherscan.io/introduction), [token transfers](https://docs.etherscan.io/api-reference/endpoint/tokentx), [logs](https://docs.etherscan.io/api-reference/endpoint/getlogs) | Current base is `https://api.etherscan.io/v2/api`, with `chainid`; token transfer parameters include `module=account`, `action=tokentx`, address/contract, block bounds, `page`, `offset`, `sort` and API key |
| Blockscout | [REST APIs](https://docs.blockscout.com/devs/apis/rest) | Verified contract source is instance-specific; the case caches source/ABI from the Ethereum instance and checks exact hashes |
| Solana | [signatures](https://solana.com/docs/rpc/http/getsignaturesforaddress), [transactions](https://solana.com/docs/rpc/http/gettransaction) | Signature cursor pagination is separate from transaction retrieval; retain finality, encoding and supported transaction version |
| CometBFT / Tellor | [RPC reference](https://docs.cosmos.network/cometbft/latest/api-reference/rpc), [block results](https://docs.cosmos.network/cometbft/latest/api-reference/rpc/info/block_results), [indexing](https://docs.cosmos.network/cometbft/latest/docs/app-dev/Indexing-Transactions) | Pin height; `tx_search` depends on node indexing; full block-result scans are a distinct collection path |
| DIA Lasernet | [chain information](https://www.diadata.org/docs/dia-stack/architecture/core-components/lasernet/chain-information) | Mainnet chain ID 1050 and `https://rpc.diadata.org/`; historical log capacity must be checked with the provider |
| Tellor endpoint | [official node setup](https://docs.tellor.io/tellor/running-tellor/node-setup) | The documented mainnet RPC is `https://mainnet.tellorlayer.com/rpc/`; this does not establish complete archival event indexing |
| Flare | [network overview](https://dev.flare.network/network/overview) | Mainnet chain ID 14 and `https://flare-api.flare.network/ext/C/rpc`; historical capacity remains provider-specific |

The Etherscan comparison is not an additional data source in the runnable case. An API status `0` can mean failure or no matching records; HTTP 200 alone is insufficient. No explorer label is converted into factual correctness.

## Failure behavior

The default replay stops on missing or changed input bytes. Public-download allows four HTTP attempts (30-second timeout, 1/2/4-second delays), bounds byte counts and checks SHA256. It never substitutes missing data with an empty table. Live case RPC checks chain identity and a known transaction before use; each call allows four attempts. Headers/receipts must match the frozen specification; provider identity is recorded without credentials. A latest-code fallback is explicitly recorded and cannot establish historical runtime identity.

Historical full collectors have different retry policies, retained in the acquisition profiles. A failover endpoint must match the chain and historical block evidence. Completed segment markers support resumption, but stale markers are not a substitute for checking source completeness. API keys belong in user environment variables; do not place them in notebooks or committed reports.
