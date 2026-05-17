"""
测试 LLM 模块
"""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from core.llm import (
    LLMMessage,
    LLMResponse,
    LLMConfig,
    LLMError,
    LLMParseError,
    DeepSeekProvider,
    OllamaProvider,
    create_provider,
    parse_llm_json,
    parse_llm_json_list,
    with_retry,
)


class TestLLMMessage:
    """测试 LLMMessage 数据结构"""
    
    def test_to_dict(self):
        msg = LLMMessage(role="user", content="Hello")
        assert msg.to_dict() == {"role": "user", "content": "Hello"}
    
    def test_roles(self):
        for role in ["system", "user", "assistant"]:
            msg = LLMMessage(role=role, content="test")
            assert msg.role == role


class TestLLMConfig:
    """测试 LLMConfig 配置"""
    
    def test_default_values(self):
        config = LLMConfig(
            api_key="test-key",
            base_url="http://localhost:11434/v1",
            model="llama3.1"
        )
        assert config.temperature == 0.7
        assert config.max_tokens == 8192


class TestDeepSeekProvider:
    """测试 DeepSeek Provider"""
    
    @patch('core.llm.OpenAI')
    def test_init(self, mock_openai):
        config = LLMConfig(
            api_key="test-key",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat"
        )
        provider = DeepSeekProvider(config)
        assert provider.config == config
        mock_openai.assert_called_once()
    
    @patch('core.llm.OpenAI')
    def test_complete(self, mock_openai):
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test response"))]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20)
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        config = LLMConfig(
            api_key="test-key",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat"
        )
        provider = DeepSeekProvider(config)
        
        messages = [LLMMessage(role="user", content="Hello")]
        response = provider.complete(messages)
        
        assert response.content == "Test response"
        assert response.input_tokens == 10
        assert response.output_tokens == 20


class TestOllamaProvider:
    """测试 Ollama Provider"""
    
    @patch('core.llm.OpenAI')
    def test_init_default(self, mock_openai):
        provider = OllamaProvider()
        assert provider.config.api_key == "ollama"
        assert provider.config.base_url == "http://localhost:11434/v1"
        assert provider.config.model == "llama3.1"
    
    @patch('core.llm.OpenAI')
    def test_init_custom_config(self, mock_openai):
        config = LLMConfig(
            api_key="custom-key",
            base_url="http://custom:11434/v1",
            model="custom-model"
        )
        provider = OllamaProvider(config)
        assert provider.config.api_key == "custom-key"
        assert provider.config.base_url == "http://custom:11434/v1"
    
    @patch('core.llm.OpenAI')
    def test_init_from_env(self, mock_openai):
        with patch.dict(os.environ, {
            'OLLAMA_BASE_URL': 'http://env-host:11434/v1',
            'OLLAMA_MODEL': 'env-model'
        }):
            provider = OllamaProvider()
            assert provider.config.base_url == "http://env-host:11434/v1"
            assert provider.config.model == "env-model"
    
    @patch('core.llm.OpenAI')
    def test_complete(self, mock_openai):
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Ollama response"))]
        mock_response.usage = Mock(prompt_tokens=5, completion_tokens=10)
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        provider = OllamaProvider()
        messages = [LLMMessage(role="user", content="Test")]
        response = provider.complete(messages)
        
        assert response.content == "Ollama response"
        assert response.input_tokens == 5


class TestCreateProvider:
    """测试 Provider 工厂函数"""
    
    @patch('core.llm.OpenAI')
    def test_create_deepseek_default(self, mock_openai):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test-key'}):
            provider = create_provider()
            assert isinstance(provider, DeepSeekProvider)
    
    @patch('core.llm.OpenAI')
    def test_create_ollama_explicit(self, mock_openai):
        provider = create_provider(provider_type="ollama")
        assert isinstance(provider, OllamaProvider)
    
    @patch('core.llm.OpenAI')
    def test_create_from_env(self, mock_openai):
        with patch.dict(os.environ, {'LLM_PROVIDER': 'ollama'}):
            provider = create_provider()
            assert isinstance(provider, OllamaProvider)


class TestParseLLMJSON:
    """测试 JSON 解析函数"""
    
    def test_parse_simple_json(self):
        from pydantic import BaseModel
        
        class TestSchema(BaseModel):
            name: str
            age: int
        
        raw = '{"name": "Alice", "age": 30}'
        result = parse_llm_json(raw, TestSchema)
        assert result.name == "Alice"
        assert result.age == 30
    
    def test_parse_json_with_code_block(self):
        from pydantic import BaseModel
        
        class TestSchema(BaseModel):
            value: str
        
        raw = '```json\n{"value": "test"}\n```'
        result = parse_llm_json(raw, TestSchema)
        assert result.value == "test"
    
    def test_parse_invalid_json(self):
        from pydantic import BaseModel
        
        class TestSchema(BaseModel):
            name: str
        
        raw = 'invalid json'
        with pytest.raises(LLMParseError) as exc_info:
            parse_llm_json(raw, TestSchema)
        assert "JSON 解析失败" in str(exc_info.value)
    
    def test_parse_list(self):
        from pydantic import BaseModel
        
        class Item(BaseModel):
            id: int
        
        raw = '[{"id": 1}, {"id": 2}]'
        result = parse_llm_json_list(raw, Item)
        assert len(result) == 2
        assert result[0].id == 1


class TestWithRetry:
    """测试重试装饰器"""
    
    def test_success_no_retry(self):
        call_count = [0]
        def fn():
            call_count[0] += 1
            return "success"
        
        result = with_retry(fn, max_attempts=3)
        assert result == "success"
        assert call_count[0] == 1
    
    def test_retry_on_failure(self):
        call_count = [0]
        def fn():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = with_retry(fn, max_attempts=3, delay_seconds=0.01)
        assert result == "success"
        assert call_count[0] == 3
    
    def test_max_retries_exceeded(self):
        def fn():
            raise ValueError("Persistent error")
        
        with pytest.raises(ValueError):
            with_retry(fn, max_attempts=2, delay_seconds=0.01)
