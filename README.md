# Charli3 Offchain Core

This repository explores the use of pycardano in the Charli3 Oracle implementation. It covers minting tokens, implementing datums, redeemers, and Node off-chain transactions in Python. It now leverages the charli3-offchain-core package, which contains shared code that is used across different private repositories of the Charli3 oracle network.
### Compatible charli3-oracle-prototype Branches
- [main](https://github.com/Charli3-Official/charli3-oracle-prototype/tree/main)

## Getting Started
### Prerequisites
- Python 3.10
- This project uses Poetry to manage dependencies. If you don't have Poetry installed, you can install it by following the instructions at [Poetry documentation](https://python-poetry.org/docs/).

### Installation
1. Clone the repository:
```bash
git clone https://github.com/Charli3-Official/charli3-offchain-core.git
```
2. Change to the repository's directory:
```bash
cd charli3-offchain-core
```
3. Install dependencies using Poetry:
```bash
poetry install
```
4. To Install the `charli3-offchain-core` package. Replace `<username>` and `<token>` with your GitHub username and a personal access token that has the `read:packages` scope:
```bash
poetry add git+https://<username>:<token>@github.com/Charli3-Official/charli3-offchain-core.git
```
Note: This package is hosted privately on GitHub. To install it, you need to provide your GitHub username and a personal access token that has the read:packages scope.

# Oracle Deployment Guide

This guide walks you through the steps to deploy an oracle on the Cardano blockchain using Python.

## Prepare binary file (if it is updated)

Binary executable is packed into .zip archive and stored at `binary/serialized.zip`. If the oracle validator is changed, you need to update this file: either download it from release [assets](https://github.com/Charli3-Official/charli3-oracle-prototype/releases), or manually build & pack `cabal build serialized && zip -j serialized.zip $(cabal list-bin serialized)`.

## Create the configuration file
Create a oracle_deploy.yml file in the root directory of the project. This file contains the configuration needed to deploy the oracle. Fill it with your specific values.

Here is an example of what it should look like: [sample-oracle-deploy.yml](sample-oracle-deploy.yml)

## Run the oracle deployment script
Finally, you can deploy the oracle by running the main script.
```bash
python3 scripts/oracle_deploy.py
```
Remember to the `oracle_deploy.yml` file should be filled with your own values for the oracle. The mnemonic should be your 24-word mnemonic for your wallet, and other values should match your specific use-case and the state of the Cardano blockchain at the time of deployment.

**Note: Currently Supported Derivation Path For Mnemonic**

The backend of this application currently supports the default initial path, which is the standard path used when setting up a new wallet. The derivation path "m/1852'/1815'/0'/0/0" is employed to generate the necessary keys and addresses.

# Oracle Owner CLI
This repository provides a command line interface (CLI) for managing oracle owner actions.
``` bash
$ python3 scripts/oracle_owner_actions.py --help
Usage: oracle_owner_actions.py [OPTIONS] COMMAND [ARGS]...

  A CLI for managing the oracle owner actions.

Options:
  --help  Show this message and exit.

Commands:
  add-funds                Add funds to the oracle.
  add-nodes                Add nodes to the oracle interactively.
  create-reference-script  Create the reference script.
  edit-settings            Interactively edit the oracle settings.
  oracle-close             Close the oracle.
  platform-collect         Collect the oracle's platform rewards.
  remove-nodes             Remove nodes from the oracle interactively.
```
## How to Use
The CLI is built with Python and uses Click library to manage the commands.

You can use the CLI to perform actions like adding nodes, removing nodes, adding funds, and editing settings of the oracle.

Before running the CLI, you will need to set up your configuration in the [oracle-owner-actions.yml](sample-oracle-owner-actions.yml) file.

Below are the available commands:

1. `add-funds`: Interactively adds nodes to the oracle. The program will prompt you to enter nodes. To quit, enter 'q'.

    ```bash
    python scripts/oracle_owner_actions.py add-funds
    ```
2. `remove-nodes`: Interactively removes nodes from the oracle. The program will prompt you to enter nodes. To quit, enter 'q'.

    Limitation : Make sure Wallet doesn't have C3 tokens or spceifically tx doesn't output C3 tokens while building, The validator checks for payment tokens (C3) Output and if it's more than the node rewards amount it will fail.
    ```
    python scripts/oracle_owner_actions.py remove-nodes
    ```
3. `add-funds`: Adds funds to the oracle with Integer Arg.

    ```
    python scripts/oracle_owner_actions.py add-funds 500
    ```
4. `oracle-close`: Closes the oracle.

    ```
    python scripts/oracle_owner_actions.py oracle-close
    ```

5. `platform-collect`: Collects the oracle's platform rewards.

    ```
    python scripts/oracle_owner_actions.py platform-collect
    ```

6. `create-reference-script`: Creates the reference script UTxO.

    ```
    python scripts/oracle_owner_actions.py create-reference-script
    ```

7. `edit-settings`: Interactively edit the oracle settings. The program will prompt you to enter the number corresponding to the setting you want to change, and then the new value for that setting. To finish and apply changes, enter 'q'.

    ```
    python scripts/oracle_owner_actions.py edit-settings
    ```


# Run Nodes Simulator

## Setup & Execution
1. Before running the CLI, you will need to set up your configuration in the [run-node-simulator.yml](sample-run-node-simulator.yml) file.
2. Update the updates list in the yaml with your own mnemonic phrases and update values.
3. Run the script by typing
   ```
    python scripts/run_simulation.py
    ```
4. The script will print the public key hash of each node it creates, perform the updates for each node, aggregate the oracle with last node, and collect reward for each node with a 20-second delay between each collection.

## Modules
### Minting Tokens
Explore the minting tokens module in the following files:
- [charli3_offchain_core/mint.py](charli3_offchain_core/mint.py)
- [charli3_offchain_core/run_minting.py](charli3_offchain_core/run_minting.py)
### Datums Implementation
Check out the implementation of datums in Python in the following file:
- [charli3_offchain_core/datums.py](charli3_offchain_core/datums.py)
### Redeemers Implementation
Check out the implementation of redeemers in Python in the following file:
- [charli3_offchain_core/redeemers.py](charli3_offchain_core/redeemers.py)
### Node Operator Off-Chain Transactions
Check out the implementation of Node off-chain transactions in Python in the following file:
- [charli3_offchain_core/node.py](charli3_offchain_core/node.py)
### Oracle Owner (Admin) Off-Chain Transactions
Check out the implementation of Oracle Owner off-chain transactions in Python in the following file:
- [charli3_offchain_core/oracle_owner.py](charli3_offchain_core/oracle_owner.py)

### ChainQuery
[Chainquery](charli3_offchain_core/chain_query.py) contains code for interacting with the Cardano blockchain.


## Building the Package
The `charli3-offchain-core` package uses Poetry for dependency management and building. Here are the steps to build the package:
1. Navigate to the root directory of the repository:
```bash
cd charli3-offchain-core
```
2. To build the package, run:
```bash
poetry build
```
This will generate a .tar.gz and a .whl file in the dist/ directory, which can be distributed and installed.

## Importing the Package into Other Repositories
To import the charli3-offchain-core package into other repositories:

1. Navigate to the root directory of the other repository.
2. Make sure Poetry is installed in the current environment. If not, follow the installation guide in the [Prerequisites](#prerequisites) section.
3. Add the `charli3-offchain-core` package using Poetry. Replace `<username>` and `<token>` with your GitHub username and a personal access token that has the `read:packages` scope:
```bash
poetry add git+https://<username>:<token>@github.com/Charli3-Official/charli3-offchain-core.git
```
4. After successful installation, you can import the package into your Python files like any other Python package. For example:
```python
from charli3_offchain_core import mint, datums, redeemers, node
```
Remember to replace `<username>` and `<token>` with your actual GitHub username and token.

