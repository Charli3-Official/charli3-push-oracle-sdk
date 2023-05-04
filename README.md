# charli3-pycardano

This repository explores the use of pycardano in the Charli3 Oracle implementation. It covers minting tokens, implementing datums, redeemers, and Node off-chain transactions in Python.

## Getting Started
### Prerequisites
- Python 3.10
- This project uses Poetry to manage dependencies. If you don't have Poetry installed, you can install it by following the instructions at [Poetry documentation](https://python-poetry.org/docs/).

To install the required Python packages, run:

```
poetry install
```

### Installation
1. Clone the repository:
```
git clone https://github.com/Charli3-Official/charli3-pycardano.git
```
2. Change to the repository's directory:
```
cd charli3-pycardano
```
3. Install dependencies using Poetry:
```
poetry install
```

## Modules
### Minting Tokens
Explore the minting tokens module in the following files:
- [src/mint.py](src/mint.py)
- [src/run_minting.py](src/run_minting.py)
### Datums Implementation
Check out the implementation of datums in Python in the following file: 
- [src/datums.py](src/datums.py)
### Redeemers Implementation
Check out the implementation of redeemers in Python in the following file:
- [src/redeemers.py](src/redeemers.py)
### Node Operator Off-Chain Transactions
Check out the implementation of Node off-chain transactions in Python in the following file: 
- [src/node.py](src/node.py)
### Oracle Owner (Admin) Off-Chain Transactions
Check out the implementation of Oracle Owner off-chain transactions in Python in the following file:
- [src/oracle_owner.py](src/oracle_owner.py)

### ChainQuery 
[Chainquery](src/chain_query.py) contains code for interacting with the Cardano blockchain.
