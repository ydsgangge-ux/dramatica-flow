"""
集成测试 - 测试完整的工作流程
"""
import os
import pytest
import tempfile
import shutil
from pathlib import Path
from core.state import StateManager
from core.types.state import BookConfig
from datetime import datetime, timezone


class TestIntegration:
    """集成测试"""
    
    @pytest.fixture
    def temp_project(self):
        """创建临时项目目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_create_book(self, temp_project):
        """测试创建书籍完整流程"""
        # 创建书籍配置
        book_id = "test_book"
        config = BookConfig(
            id=book_id,
            title="测试书籍",
            genre="玄幻",
            target_words_per_chapter=4000,
            target_chapters=10,
            protagonist_id="protagonist",
            status="planning",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        # 初始化状态管理器
        sm = StateManager(temp_project, book_id)
        sm.init(config)
        
        # 验证文件创建
        assert (Path(temp_project) / "books" / book_id / "state" / "config.json").exists()
        assert (Path(temp_project) / "books" / book_id / "chapters").exists()
        
        # 读取配置验证
        loaded_config = sm.read_config()
        assert loaded_config["title"] == "测试书籍"
        assert loaded_config["genre"] == "玄幻"
    
    def test_save_and_read_chapter(self, temp_project):
        """测试保存和读取章节"""
        book_id = "test_book"
        config = BookConfig(
            id=book_id,
            title="测试书籍",
            genre="玄幻",
            target_words_per_chapter=4000,
            target_chapters=10,
            protagonist_id="protagonist",
            status="planning",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        sm = StateManager(temp_project, book_id)
        sm.init(config)
        
        # 保存草稿
        chapter_content = "# 第一章 测试\n\n这是测试内容。"
        sm.save_draft(1, chapter_content)
        
        # 读取草稿
        loaded_content = sm.read_draft(1)
        assert loaded_content == chapter_content
        
        # 保存最终稿
        sm.save_final(1, chapter_content + "\n\n修订完成。")
        
        # 读取最终稿
        final_content = sm.read_final(1)
        assert "修订完成" in final_content
    
    def test_world_state(self, temp_project):
        """测试世界状态管理"""
        book_id = "test_book"
        config = BookConfig(
            id=book_id,
            title="测试书籍",
            genre="玄幻",
            target_words_per_chapter=4000,
            target_chapters=10,
            protagonist_id="protagonist",
            status="planning",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        sm = StateManager(temp_project, book_id)
        sm.init(config)
        
        # 读取初始世界状态
        ws = sm.read_world_state()
        assert ws.current_chapter == 0
        
        # 更新世界状态
        ws.current_chapter = 5
        sm.save_world_state(ws)
        
        # 重新读取验证
        ws_loaded = sm.read_world_state()
        assert ws_loaded.current_chapter == 5


class TestOllamaIntegration:
    """Ollama 集成测试"""
    
    def test_ollama_provider_creation(self):
        """测试 Ollama Provider 创建"""
        from core.llm import OllamaProvider, create_provider
        
        # 直接创建
        provider = OllamaProvider()
        assert provider.config.base_url == "http://localhost:11434/v1"
        assert provider.config.model == "llama3.1"
        
        # 通过工厂创建
        provider2 = create_provider(provider_type="ollama")
        assert isinstance(provider2, OllamaProvider)
    
    def test_ollama_custom_config(self):
        """测试 Ollama 自定义配置"""
        from core.llm import OllamaProvider, LLMConfig
        
        config = LLMConfig(
            api_key="custom",
            base_url="http://custom-host:11434/v1",
            model="mistral",
            temperature=0.8
        )
        
        provider = OllamaProvider(config)
        assert provider.config.base_url == "http://custom-host:11434/v1"
        assert provider.config.model == "mistral"
        assert provider.config.temperature == 0.8
    
    def test_ollama_env_config(self):
        """测试从环境变量配置 Ollama"""
        from core.llm import OllamaProvider
        import os
        
        original_url = os.environ.get("OLLAMA_BASE_URL")
        original_model = os.environ.get("OLLAMA_MODEL")
        
        try:
            os.environ["OLLAMA_BASE_URL"] = "http://env-host:11434/v1"
            os.environ["OLLAMA_MODEL"] = "codellama"
            
            provider = OllamaProvider()
            assert provider.config.base_url == "http://env-host:11434/v1"
            assert provider.config.model == "codellama"
        finally:
            if original_url:
                os.environ["OLLAMA_BASE_URL"] = original_url
            elif "OLLAMA_BASE_URL" in os.environ:
                del os.environ["OLLAMA_BASE_URL"]
            
            if original_model:
                os.environ["OLLAMA_MODEL"] = original_model
            elif "OLLAMA_MODEL" in os.environ:
                del os.environ["OLLAMA_MODEL"]
