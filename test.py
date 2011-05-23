import asyncore
from collections import deque
from lib import HTTPAsyncClient


def test_get_status():
    """Test get_status from HTTPAsyncClient"""
    header = "HTTP/1.1 200 OK\r\nDate: Mon, 23 May 2011 02:34:37 GMT\r\n\
        Server: Apache/2.2.3 (CentOS)\r\n"
    assert HTTPAsyncClient.get_status(header) == "200"
    header = "HTTP/1.1 301 Moved Permanently"
    assert HTTPAsyncClient.get_status(header) == "301"
    header = "HTTP/1.1 400 Bad Request"
    assert HTTPAsyncClient.get_status(header) == "400"
    header = "HTTP/1.1 404 Not Found"
    assert HTTPAsyncClient.get_status(header) == "404"
    header = "HTTP/1.1 500 Internal Server Error"
    assert HTTPAsyncClient.get_status(header) == "500"

def test_get_body():
    """Test get_body from HTTPAsyncClient"""
    chunk = "100\r\nBody chunk data\r\n0"
    assert HTTPAsyncClient.get_body(chunk) == "Body chunk data"
    chunk = "BODY"
    assert HTTPAsyncClient.get_body(chunk) == "BODY"

def test_request(capsys):
    """Test a request by checking the output"""
    HTTPAsyncClient("en.wikipedia.org", deque(["/"]))
    asyncore.loop()
    out, err = capsys.readouterr()
    assert "Status: 301" in out
    HTTPAsyncClient("en.wikipedia.org", deque(["/wiki/Berlin"]))
    asyncore.loop()
    out, err = capsys.readouterr()
    assert "Status: 200" in out
    HTTPAsyncClient("www.cs.uni-potsdam.de", deque(["/Berlin"]))
    asyncore.loop()
    out, err = capsys.readouterr()
    assert "Status: 404" in out
