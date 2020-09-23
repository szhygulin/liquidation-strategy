# Usage
- specify eth node's rpc access point in server.py
- run server.py on the local or remote server
- specify the server IP and port in pooler.py
- specify sender's acount details in pooler.py
- specify contract address and path to abi file in pooler.py
- specify threshold for liquidation profitability in pooler.py
- run pooler.py

# Response
Pooler runs infinite cycle, periodically asking server for underwater accounts - liauidation candidates. If expected profitability exceeds provided threshold, pooler sends liquidation transaction to the smart contract, specifying the data for liquidation with the biggest expected return. Paused for specified tx confrimation time, then continues. If the server provided liquidation candidate with exactly the same data as the last sent transaction, pooler skips sending tx.

# Misc
Pooler use ethgasstation oracle for gas price, picking the entry for fastest confirmation

# Updating Token Holders
For every listed cToken download csv file of token holders from etherscan.io and replace corresponding file in token_holders directory.

# Adding New Token
Add new token details in the Copmpound.json file under "tokens" field.
