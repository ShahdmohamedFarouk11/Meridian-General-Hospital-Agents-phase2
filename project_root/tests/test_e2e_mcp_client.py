import pytest
from unittest.mock import AsyncMock, MagicMock
from mcp_client import LawFirmMCPClient
from fastmcp.client.transports import ClientTransport
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import MagicMock

class InnerFastMCPTransport(ClientTransport):
    """ClientTransport حقيقي لـ FastMCP لتخطي validation وتجنب Abstract Class error"""
    @asynccontextmanager
    async def connect_session(self) -> AsyncGenerator[MagicMock, None]:
        mock_session = MagicMock()
        yield mock_session

class DummyTransport:
    """Wrapper يتوافق مع توقعات LawFirmMCPClient ويحوي دالة create"""
    def create(self) -> ClientTransport:
        return InnerFastMCPTransport()
@pytest.mark.asyncio
async def test_mcp_client_handshake_and_capabilities():
    mock_transport = DummyTransport()
    client = LawFirmMCPClient(transport=mock_transport)
    
    # Mock FastMCP Session & Capabilities
    client.client.__aenter__ = AsyncMock()
    client.client.__aexit__ = AsyncMock()
    
    mock_capabilities = MagicMock()
    mock_capabilities.tools = {}
    mock_capabilities.resources = {}
    mock_capabilities.prompts = None
    
    from unittest.mock import PropertyMock  # أضف الاستيراد في أعلى الملف إن لم يكن موجوداً

    mock_session = MagicMock()
    type(client.client).session = PropertyMock(return_value=mock_session)
    client.client.session.get_server_capabilities.return_value = mock_capabilities
    client.client.list_tools = AsyncMock(return_value=[
        MagicMock(name="search_rag_documents"),
        MagicMock(name="verify_answer_grounding")
    ])
    
    # Run Initialization Handshake
    await client.initialize()
    
    assert client.connected is True
    assert client.supports("tools") is True
    assert client.supports("resources") is True
    assert client.supports("prompts") is False
    assert len(client.available_tools) == 2

@pytest.mark.asyncio
async def test_mcp_client_tool_execution_and_failure_path():
    mock_transport = DummyTransport()
    client = LawFirmMCPClient(transport=mock_transport)
    
    # Test Failure Path: Execution before connection
    with pytest.raises(RuntimeError, match="MCP client is not connected."):
        await client.call_tool("search_rag_documents", {"query": "test"})
        
    # Setup Connected state
    client.connected = True
    client.capabilities["tools"] = True
    client.client.call_tool = AsyncMock(return_value={"status": "success", "results": []})
    
    # Test Normal Path
    response = await client.call_tool("search_rag_documents", {"query": "test"})
    assert response["status"] == "success"
    
    await client.close()
    assert client.connected is False