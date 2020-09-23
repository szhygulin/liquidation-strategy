from web3 import Web3
import csv
import json
import asyncio
from aiohttp import ClientSession
import requests
import time
import random

# TODO: specify ETH node access point
url = 'http://3.130.35.241:8100'

class SmartContract:
    def __init__(self, address, abi, w3):
        self.address = Web3.toChecksumAddress(address)
        self.abi = abi
        self.w3 = w3
        self.contract = w3.eth.contract(address=self.address, abi=self.abi)


class Oracle(SmartContract):
    def __init__(self, address, abi, w3, tokens):
        super(Oracle, self).__init__(address, abi, w3)
        self.tokens = tokens

    def get_price(self, token_address):
        token_address = Web3.toChecksumAddress(token_address)
        price = self.contract.functions.getUnderlyingPrice(token_address).call()
        return price

    def get_prices(self):
        result = {}
        for x in self.tokens:
            price = self.get_price(x.address)
            result[x.symbol] = price
        return result

class Token(SmartContract):
    def __init__(self, data, w3):
        super(Token, self).__init__(data['address'], data['abi'], w3)
        print('importing symbol', data['symbol'])
        self.symbol = data['symbol']
        self.og_symbol = data['ogSymbol']
        self.decimals = data['decimals']
        self.regular_decimals = data['regularDecimals']
        self.regular_address = data['regularAddress']
        self.token_holders = []

    def get_cr_holders(self, directory):
        with open(directory + f'/export-tokenholders-for-contract-{self.address.lower()}.csv', 'r') as f:
            next(f)
            file_reader = csv.reader(f)
            for row in file_reader:
                self.token_holders.append(row)


class Compound(SmartContract):
    def __init__(self, tokens, w3, address, abi, url):
        super(Compound, self).__init__(address, abi, w3)
        self.tokens = tokens
        self.depositors = []
        self.url = url
        # TODO: keep only addresses
        for t in tokens:
            for x in t.token_holders:
                if x[0] not in self.depositors:
                    self.depositors.append([x[0]])
        self.decimals = {}
        self.regular_decimals = {}
        for x in self.tokens:
            self.decimals[x.symbol] = x.decimals
            self.regular_decimals[x.symbol] = x.regular_decimals

    @staticmethod
    def parse_result(result):
        string_data = str(result)
        string_data = str(string_data[2:])
        result = []
        while len(string_data) > 0:
            a = '0x' + string_data[0:64]
            string_data = string_data[64:]
            result.append(int(a, 0))
        return result

    # depreteated to async call
    def sc_call(self, address, data):
        #data = self.contract.functions.getAccountLiquidity(address).buildTransaction()
        data['value'] = hex(data['value'])
        data['gas'] = hex(data['gas'])
        data['gasPrice'] = hex(data['gasPrice'])
        del data['chainId']
        request_body = {'method': "eth_call",
                        'params': [data, "latest"],
                        'id': 1,
                        'jsonrpc': "2.0"}
        with requests.post(url=self.url, json=request_body) as response:
            result = response.json()
        return result

    async def async_sc_call(self, data, session):
        #time.sleep(random.randint(0, 50)/500)
        data['value'] = hex(data['value'])
        data['gas'] = hex(data['gas'])
        data['gasPrice'] = hex(data['gasPrice'])
        data['chainId'] = hex(data['chainId'])
        request_body = {'method': "eth_call",
                        'params': [data, "latest"],
                        'id': 1,
                        'jsonrpc': "2.0"}
        async with session.post(url, json=request_body) as response:
            result = await response.json()
        try:
            result2 = result['result']
            if result2 != '0x':
                return Compound.parse_result(result2)
            else:
                print("empty result on request: ", data['data'], result)
                print('Most likely not enough gas')
                return [0, 0, 0, 0]
        except:
            print("Error: ", result)
            return [0, 0, 0, 0]

    async def async_sc_bounded(self, sem, address, session, data, contract, method):
        async with sem:
            response = await self.async_sc_call(data, session)
            #return [address, contract, method, response]
            return {'address': address, 'contract': contract, 'method': method, 'response': response}

    async def get_comptroller_batched(self):
        sem = asyncio.Semaphore(1000)
        tasks = []
        async with ClientSession() as session:
            print("amount of addresses: ", len(self.depositors))
            for n, x in enumerate(self.depositors):
                address = Web3.toChecksumAddress(x[0])
                # data = y.contract.functions.getAccountLiquidity(address).buildTransaction()
                data = {'value': 0,
                        'gas': 122868300,
                        'gasPrice': 290000000000,
                        'chainId': 1,
                        'to': '0x3d5BC3c8d13dcB8bF317092d84783c2697AE9258',
                        'data': '0x5ec88c79000000000000000000000000' + address.lower()[2:]}
                task = asyncio.ensure_future(
                    self.async_sc_bounded(sem, address, session, data, 'compound', 'liquidity'))
                tasks.append(task)
            print('Tasks are formed')
            response = await asyncio.gather(*tasks)
        return response

    async def get_tokens_batched(self):
        sem = asyncio.Semaphore(1000)
        tasks = []
        async with ClientSession() as session:
            print("after elimination, amount of addresses: ", len(self.depositors))
            for n, x in enumerate(self.depositors):
                address = Web3.toChecksumAddress(x[0])
                for y in self.tokens:
                    #data = y.contract.functions.getAccountSnapshot(address).buildTransaction()
                    data = {'value': 0,
                            'gas': 3651600,
                            'gasPrice': 309000000000,
                            'chainId': 1,
                            'to': y.address,
                            'data': '0xc37f68e2000000000000000000000000' + address.lower()[2:]}
                    task = asyncio.ensure_future(
                        self.async_sc_bounded(sem, address, session, data, y.symbol, 'snapshot'))
                    tasks.append(task)
            print('Tasks are formed')
            response = await asyncio.gather(*tasks)
        return response

    def retrieve_data(self):
        response1 = asyncio.run(self.get_comptroller_batched())
        print("Accounts liquidity retrieved")
        to_be_liquidated = []
        to_be_monitored = []
        for x in response1:
            if x['response'][2] == 0:
                if x['response'][1] <= 10 ** 18 and x['response'][1] > 0:
                    to_be_monitored.append([x['address'].lower()])
                del self.depositors[self.depositors.index([x['address'].lower()])]
            else:
                to_be_monitored.append([x['address'].lower()])
                to_be_liquidated.append(x)
        with open('monitored.json', 'w') as f:
            json.dump(to_be_monitored, f, indent=4)
        response2 = asyncio.run(self.get_tokens_batched())
        response = to_be_liquidated + response2
        print("crToken snapshots data retrieved")
        return response

    def retrieve_data_cached(self):
        with open('monitored.json', 'r') as f:
            addresses = json.load(f)
        self.depositors = addresses
        response = self.retrieve_data()
        return response

    def parse_and_dump_data(self, response, prices):
        accounts = {}
        # form the bones
        for x in self.depositors:
            dic = {}
            dic['address'] = x[0].lower()
            dic["block_updated"] = None
            dic['health'] = 0
            dic['tokens'] = {}
            dic['shortfall'] = 0
            for y in self.tokens:
                temp = {}
                temp['address'] = y.address
                temp['symbol'] = y.symbol
                temp['lifetime_borrow_interest_accrued'] = 0
                temp['lifetime_supply_interest_accrued'] = 0
                temp['safe_withdraw_amount_underlying'] = 0
                temp['supply_balance_underlying'] = 0
                temp['borrow_balance_underlying'] = 0
                dic['tokens'][y.symbol] = temp
            dic['total_borrow_value_in_eth'] = 0
            dic['total_collateral_value_in_eth'] = 0
            accounts[x[0].lower()] = dic
        # put the muscles
        for x in response:
            address = x['address'].lower()
            if x['contract'] == 'compound':
                if x['response'][2] > 0:
                    accounts[address]['health'] = 0
                    accounts[address]['shortfall'] = x['response'][2]
                else:
                    accounts[address]['health'] = 3
            else:
                token = x['contract']
                supply = (x['response'][1])
                borrow = (x['response'][2])
                mantissa = x['response'][3]
                # update token borrow and supply
                accounts[address]['tokens'][token]['supply_balance_underlying'] = supply
                accounts[address]['tokens'][token]['borrow_balance_underlying'] = borrow
                # calculate these values in eth denom
                s_eth = supply * mantissa * prices[token] / (10**(18*3))
                b_eth = borrow * prices[token] / (10 ** 36)
                accounts[address]['tokens'][token]['supply_balance_eth'] = s_eth
                accounts[address]['tokens'][token]['borrow_balance_eth'] = b_eth
                accounts[address]['tokens'][token]['mantissa'] = mantissa
                # update total account's borrow and supply
                accounts[address]['total_borrow_value_in_eth'] += b_eth
                accounts[address]['total_collateral_value_in_eth'] += b_eth
        # push data to list for sorting
        accounts_list = []
        for key in accounts:
            entry = accounts[key]
            tokens = []
            for y_key in accounts[key]['tokens']:
                tokens.append(accounts[key]['tokens'][y_key])
            entry['tokens'] = tokens
            accounts_list.append(entry)
        accounts_sorted = sorted(accounts_list, key = lambda k: k['total_borrow_value_in_eth'], reverse=True)
        with open('data.json', "w") as f:
            json.dump(accounts_sorted, f, indent=4)
        return accounts_sorted


if __name__ == "__main__":
    # establish connection

    url = url
    w3 = Web3(Web3.HTTPProvider(url))
    print("is connected:", w3.isConnected())
    print("Latest known block is:", w3.eth.getBlock('latest')['number'])

    with open('Compound.json', 'r') as comp_f:
        constants = json.load(comp_f)
    comptroller_address = Web3.toChecksumAddress(constants['comptrollerAddress'])
    tokens = []
    # initiate tokens
    for x in constants['tokens']:
        token = Token(x, w3)
        token.get_cr_holders('token_holders')
        tokens.append(token)
    compound = Compound(tokens, w3, comptroller_address, constants['comptrollerAbi'], url)
    oracle = Oracle(constants['oracleAddress'], constants['oracleAbi'], w3, tokens)
    prices = oracle.get_prices()
    response = compound.retrieve_data()
    data = compound.parse_and_dump_data(response, prices)

    liquidations = []
    for x in data:
        liquidation = {}
        max_borrow = 0
        max_supply = 0
        for token in x['tokens']:
            if token['borrow_balance_eth'] > max_borrow:
                max_borrow = token['borrow_balance_eth']
                liquidation['borrower'] = x['address']
                liquidation['cTokenBorrowed'] = token['address']
                liquidation['cTokenBorrowed_symbol'] = token['symbol']
                # TODO: use data from SC, instead of 50% and 8% hardcoded
                liquidation['actualRepayAmount'] = int(token['borrow_balance_underlying'] / 2)
                liquidation['to_be_taken_from_collateral'] = max_borrow / 2 * 1.08
                liquidation['expected_profit'] = max_borrow / 2 * 0.08
        for token in x['tokens']:
            if token['supply_balance_eth'] > max_supply and token['symbol'] != liquidation['cTokenBorrowed_symbol']:
                max_supply = token['supply_balance_eth']
                liquidation['cTokenCollateral'] = token['address']
                liquidation['cTokenCollateral_symbol'] = token['symbol']
                liquidation['this_collateral'] = max_supply
        try:
            if liquidation['this_collateral'] > liquidation['to_be_taken_from_collateral']:
                liquidations.append(liquidation)
            else:
                coef = liquidation['this_collateral'] / liquidation['to_be_taken_from_collateral']
                liquidation['actualRepayAmount'] = int(liquidation['actualRepayAmount'] * coef * 0.99)
                liquidation['to_be_taken_from_collateral'] = liquidation['this_collateral']
                liquidation['expected_profit'] = liquidation['to_be_taken_from_collateral'] * 0.08 / 1.08
                liquidations.append(liquidation)
        except:
            print("No collateral beyond same as borrow")
            print(liquidation)
            #print(x)
        liquidations = sorted(liquidations, key=lambda k: k['to_be_taken_from_collateral'], reverse=True)

    with open('result.json', "w") as f:
        json.dump(liquidations, f, indent=4)