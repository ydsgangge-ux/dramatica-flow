"""
测试 Web Server API
"""
import pytest
from fastapi.testclient import TestClient
from core.server import app


client = TestClient(app)


class TestBooksAPI:
    """测试书籍相关 API"""
    
    def test_list_books(self):
        """测试获取书籍列表"""
        response = client.get("/api/books")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_book_not_found(self):
        """测试获取不存在的书籍"""
        response = client.get("/api/books/nonexistent_book")
        assert response.status_code == 404


class TestChaptersAPI:
    """测试章节相关 API"""
    
    def test_list_chapters_not_found(self):
        """测试获取不存在书籍的章节"""
        response = client.get("/api/books/nonexistent/chapters")
        assert response.status_code == 404
    
    def test_get_chapter_not_found(self):
        """测试获取不存在的章节"""
        response = client.get("/api/books/nonexistent/chapters/1")
        assert response.status_code == 404


class TestCausalChainAPI:
    """测试因果链 API"""
    
    def test_get_causal_chain_not_found(self):
        """测试获取不存在书籍的因果链"""
        response = client.get("/api/books/nonexistent/causal-chain")
        assert response.status_code == 404


class TestEmotionalArcsAPI:
    """测试情感弧线 API"""
    
    def test_get_emotional_arcs_not_found(self):
        """测试获取不存在书籍的情感弧线"""
        response = client.get("/api/books/nonexistent/emotional-arcs")
        assert response.status_code == 404


class TestHooksAPI:
    """测试伏笔 API"""
    
    def test_get_hooks_not_found(self):
        """测试获取不存在书籍的伏笔"""
        response = client.get("/api/books/nonexistent/hooks")
        assert response.status_code == 404


class TestRelationshipsAPI:
    """测试关系网络 API"""
    
    def test_get_relationships_not_found(self):
        """测试获取不存在书籍的关系网络"""
        response = client.get("/api/books/nonexistent/relationships")
        assert response.status_code == 404


class TestOutlineAPI:
    """测试大纲 API"""
    
    def test_get_outline_not_found(self):
        """测试获取不存在书籍的大纲"""
        response = client.get("/api/books/nonexistent/outline")
        assert response.status_code == 404
    
    def test_get_chapter_outlines_not_found(self):
        """测试获取不存在书籍的章纲"""
        response = client.get("/api/books/nonexistent/chapter-outlines")
        assert response.status_code == 404
