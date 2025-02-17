import json
import logging
import pytest
import requests
from requests import Response
from cryptoadvance.specter.rpc import BitcoinRPC, RpcError
from cryptoadvance.specter.specter_error import SpecterError

# To investigate the Bitcoin API, here are some great resources:
# https://bitcoin.org/en/developer-reference#bitcoin-core-apis
# https://chainquery.com/bitcoin-cli
# https://github.com/ChristopherA/Learning-Bitcoin-from-the-Command-Line


class CustomResponse(Response):
    """We need to fake the Response if we have to handle errors. As a Response object is not able
    to be initialized directly, we're subclassing here and create the necessary constructor
    """

    def __init__(self, status_code, json, headers):
        self.status_code = status_code
        self._content = json
        self.headers = headers
        self.encoding = None


def test_RpcError_response(caplog):
    caplog.set_level(logging.DEBUG)
    # Creating an RpcError with a Response object

    # Faking a response which looks like a Wallet has not been found
    response = requests.post(
        "https://httpbin.org/anything",
        headers={"accept": "application/json"},
        json={
            "error": {
                "message": "Requested wallet does not exist or is not loaded",
                "code": -32601,
            }
        },
    )
    response.status_code = 500
    response._content = json.dumps(
        {
            "error": {
                "message": "Requested wallet does not exist or is not loaded",
                "code": -32601,
            }
        }
    ).encode("ascii")
    assert response.status_code == 500
    assert response.json()["error"]["message"]
    rpce = RpcError("some Message", response)

    assert rpce.status_code == 500
    assert rpce.error_msg == "Requested wallet does not exist or is not loaded"
    assert rpce.error_code == -32601


def test_RpcError_response_incomplete(caplog):
    # Creating an RpcError with a Response object
    try:
        # Faking a response which looks like a Wallet has not been found
        response = requests.post(
            "https://httpbin.org/anything",
            headers={"accept": "application/json"},
            json={},
        )
        response.status_code = 500
        raise RpcError("some Message", response)
    except RpcError as rpce:
        assert rpce.status_code == 500
        assert rpce.error_code == -99
        assert rpce.error_msg.startswith("some Message")


def test_RpcError_via_params():
    # Via status_code, error_code and error_msg
    try:
        raise RpcError(
            "some Message",
            status_code=500,
            error_code=-32601,
            error_msg="Requested wallet does not exist or is not loaded",
        )
    except RpcError as rpce:
        assert rpce.status_code == 500
        assert rpce.error_code == -32601
        assert rpce.error_msg == "Requested wallet does not exist or is not loaded"

    # Only message
    try:
        raise RpcError("some message")
    except RpcError as rpce:
        assert rpce.status_code == 500
        assert rpce.error_code == -99
        assert rpce.error_msg == "some message"

    # omitting error_msg
    try:
        raise RpcError("some message", status_code=500, error_code=-32601)
    except RpcError as rpce:
        assert rpce.status_code == 500
        assert rpce.error_code == -32601
        assert rpce.error_msg == "some message"


def test_BitcoinRpc(rpc):
    result = rpc.getblockchaininfo()
    assert result.get("error") == None
    assert result["blocks"] >= 100


def test_BitcoinRpc_methodNotExisting(rpc):
    # Errorhandling:
    try:
        rpc.getSomethingNonExisting()
    except RpcError as rpce:
        assert rpce.status_code == 500
        assert rpce.error_code == -32601
        assert rpce.error_msg == "Method not found"


def test_BitcoinRpc_walletNotExisting(rpc):
    # Errorhandling:
    rpc = rpc.wallet("SomeWallet")
    try:
        rpc.getwalletinfo()
    except RpcError as rpce:
        assert rpce.status_code == 500
        assert rpce.error_code == -18
        assert rpce.error_msg == "Requested wallet does not exist or is not loaded"


def test_BitcoinRpc_timeout(rpc, caplog):
    try:
        BitcoinRPC.default_timeout = 0.001
        with pytest.raises(SpecterError) as se:
            rpc.createwallet("some_test_wallet_name_392")
        assert "Timeout after 0.001" in str(se.value)
        assert (
            "while BitcoinRPC call(                            ) payload:[{'method': 'createwallet', 'params': ['some_test_wallet_name_392'], 'jsonrpc': '2.0', 'id': 0}]"
            in caplog.text
        )

        rpc.timeout = 0.0001
        with pytest.raises(SpecterError) as se:
            rpc.createwallet("some_test_wallet_name_393")
        assert "Timeout after 0.0001" in str(se.value)
        assert "Timeout after 0.001" in caplog.text
    finally:
        BitcoinRPC.default_timeout = None


@pytest.fixture
def rpc(bitcoin_regtest):
    brt = bitcoin_regtest  # stupid long name
    BitcoinRPC.default_timeout = 0.001
    rpc = BitcoinRPC(
        brt.rpcconn.rpcuser,
        brt.rpcconn.rpcpassword,
        host=brt.rpcconn.ipaddress,
        port=brt.rpcconn.rpcport,
    )
    return rpc
