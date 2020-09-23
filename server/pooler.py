import requests
import os
import time
import json
from web3 import Web3

# TODO: specify connection to remote server collecting data
url = 'http://3.83.72.233/'

# TODO: specify sender info here
my_address = '0x390C2262A2962E44B17Bca0De0076F4b7bfD284f'
private_key = '0x390C2262A2962E44B17Bca0De0076F4b7bfD284f'

# TODO: specify contract info here
address = '0x390C2262A2962E44B17Bca0De0076F4b7bfD284f'
abi_file = "CreamKeeper.abi.json"

with open(abi_file, 'r') as f:
    abi = json.load(f)

# TODO: specify threshold parameter for assessing liquidation profitability, in ETH denomination
threshold = 0.2

# TODO: specify time variables - time interval for pooling and expected tx confirmation time, in seconds

time_interval = 30
tx_confirmation_timeout = 30

w3 = Web3(Web3.HTTPProvider(url))
contract = w3.eth.contract(address=address, abi=abi)
gas_api = 'http://ethgasstation.info/api/ethgasAPI.json'

def call_liquidation(contract, borrower, token_borrowed, token_collateral, gas_price):
    borrower = Web3.toChecksumAddress(borrower)
    token_borrowed = Web3.toChecksumAddress(token_borrowed)
    token_collateral = Web3.toChecksumAddress(token_collateral)
    params = {"from": my_address,
              "gasPrice": gas_price * 10 ** 9,
              'nonce': 1 #w3.eth.getTransactionCount(my_address)
              }
    tx = contract.functions.liquidate(borrower, token_borrowed, token_collateral)
    print(f'tx: borrower={borrower}, cTokenBorrowed={token_borrowed}, cTokenCollateral={token_collateral}, '
          f'gas_price={gas_price}')
    gas = tx.estimateGas()
    params['gas'] = gas
    tx = tx.buildTransaction(params)
    #signed = w3.eth.account.sign_transaction(tx, private_key)
    #print(str(w3.eth.sendRawTransaction(signed.rawTransaction)))

sent_tx = [0]
while True:
    #for x in new_block_filter.get_new_entries():
    data = requests.get(url=url).json()
    data2 = list(data)
    result = []
    for x in data2:
        max_rev = data[0]['expected_profit']
        if x['expected_profit'] > threshold:
            print(f"expected profit is {x['expected_profit']}, symbols - "
                  f"{x['cTokenBorrowed_symbol']}-{x['cTokenCollateral_symbol']}")
            print(x['borrower'])
            print(x['cTokenBorrowed'])
            print(x['cTokenCollateral'])
            print(x['actualRepayAmount'])
            print(x['to_be_taken_from_collateral']/1.08)
            entry = dict()
            entry['cTokenBorrowed'] = x['cTokenBorrowed']
            entry['borrower'] = x['borrower']
            entry['cTokenCollateral'] = x['cTokenCollateral']
            entry['repay_amnt'] = int(x['to_be_taken_from_collateral']/1.08 * 10 ** 18)
            entry['borrow_symbol'] = x['cTokenBorrowed_symbol']
            entry['collateral_symbol'] = x['cTokenCollateral_symbol']
            result.append(entry)
    with open('entry.json', 'w') as f:
        json.dump(result, f, indent=4)
    with open('result.json', 'w') as f:
        json.dump(data, f, indent=4)
    if result == []:
        print(f"no new signals, max profit is {data[0]['expected_profit']}")
    else:
        if sent_tx != result[0]:
            gas_price = int(requests.get(url=gas_api).json()['fastest'] / 10)
            call_liquidation(contract, result[0]['borrower'], result[0]['cTokenBorrowed'], result[0]['cTokenCollateral'], gas_price)
            sent_tx = result[0]
            time.sleep(tx_confirmation_timeout)
    time.sleep(time_interval)