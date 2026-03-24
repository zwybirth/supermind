"""
RAG Engine - 四级检索增强系统
"""

import re
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Okapi
import numpy as np


@dataclass
class Document:
    """文档对象"""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


class RAGEngine:
    """
    四级检索系统：
    1. 向量检索 (语义匹配)
    2. 关键词检索 (BM25)
    3. 重排序精排
    4. 知识图谱扩展
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.vector_store = None
        self.bm25 = None
        self.documents = []
        
        self._init_vector_store()
    
    def _init_vector_store(self):
        """初始化向量存储"""
        store_config = self.config.get('vector_store', {})
        store_type = store_config.get('type', 'chroma')
        
        if store_type == 'chroma':
            persist_dir = store_config.get('path', './data/vector_db')
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            
            self.vector_store = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=persist_dir
            ))
            
            self.collection = self.vector_store.get_or_create_collection(
                name="knowledge",
                metadata={"hnsw:space": "cosine"}
            )
    
    def add_documents(self, documents: List[Document]):
        """
        添加文档到知识库
        
        Args:
            documents: 文档列表
        """
        if not documents:
            return
        
        # 分块处理
        chunks = []
        for doc in documents:
            doc_chunks = self._chunk_document(doc)
            chunks.extend(doc_chunks)
        
        # 生成嵌入
        embeddings = self._generate_embeddings([c.content for c in chunks])
        
        # 添加到向量库
        ids = [c.id for c in chunks]
        contents = [c.content for c in chunks]
        metadatas = [c.metadata for c in chunks]
        
        self.collection.add(
            ids=ids,
            documents=contents,
            metadatas=metadatas,
            embeddings=embeddings
        )
        
        # 更新 BM25
        self.documents.extend(chunks)
        self._update_bm25()
    
    def _chunk_document(self, doc: Document) -> List[Document]:
        """文档分块"""
        chunk_size = self.config.get('chunking', {}).get('large_chunk_size', 1024)
        overlap = self.config.get('chunking', {}).get('overlap', 50)
        
        content = doc.content
        chunks = []
        
        # 简单分块策略（可优化为语义分块）
        start = 0
        chunk_idx = 0
        
        while start < len(content):
            end = min(start + chunk_size, len(content))
            
            # 尝试在句子边界截断
            if end < len(content):
                # 查找最近的句号、问号或换行
                for sep in ['. ', '? ', '! ', '\n\n', '\n']:
                    pos = content.rfind(sep, start, end)
                    if pos > start + chunk_size // 2:
                        end = pos + len(sep)
                        break
            
            chunk_content = content[start:end].strip()
            if chunk_content:
                chunk_id = f"{doc.id}_chunk_{chunk_idx}"
                chunk = Document(
                    id=chunk_id,
                    content=chunk_content,
                    metadata={**doc.metadata, 'chunk_idx': chunk_idx}
                )
                chunks.append(chunk)
                chunk_idx += 1
            
            start = end - overlap
        
        return chunks
    
    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """生成文本嵌入"""
        # 使用 sentence-transformers 或调用 embedding API
        try:
            from sentence_transformers import SentenceTransformer
            model_name = self.config.get('vector_store', {}).get(
                'embedding_model', 'BAAI/bge-large-zh-v1.5'
            )
            model = SentenceTransformer(model_name)
            embeddings = model.encode(texts, show_progress_bar=False)
            return embeddings.tolist()
        except Exception as e:
            print(f"嵌入生成失败: {e}")
            # 返回零向量作为降级
            return [[0.0] * 1024 for _ in texts]
    
    def _update_bm25(self):
        """更新 BM25 索引"""
        if not self.documents:
            return
        
        # 分词
        tokenized_docs = []
        for doc in self.documents:
            tokens = self._tokenize(doc.content)
            tokenized_docs.append(tokens)
        
        self.bm25 = BM25Okapi(tokenized_docs)
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        # 中文：按字符 + 英文单词
        tokens = []
        for char in text.lower():
            if '\u4e00' <= char <= '\u9fff':
                tokens.append(char)
            elif char.isalnum():
                tokens.append(char)
        return tokens
    
    def retrieve(self, query: str, filter: Optional[Dict] = None) -> Dict[str, Any]:
        """
        四级检索
        
        Returns:
            {
                'documents': [...],
                'vector_results': [...],
                'bm25_results': [...],
                'reranked': [...]
            }
        """
        results = {
            'documents': [],
            'vector_results': [],
            'bm25_results': [],
            'reranked': []
        }
        
        # Level 1: 向量检索
        vector_k = self.config.get('retrieval', {}).get('vector_top_k', 100)
        vector_results = self._vector_search(query, k=vector_k, filter=filter)
        results['vector_results'] = vector_results
        
        # Level 2: BM25 关键词检索
        bm25_k = self.config.get('retrieval', {}).get('bm25_top_k', 50)
        bm25_results = self._bm25_search(query, k=bm25_k)
        results['bm25_results'] = bm25_results
        
        # Level 3: 融合重排序
        rerank_k = self.config.get('retrieval', {}).get('rerank_top_k', 10)
        merged = self._reciprocal_rank_fusion(vector_results, bm25_results)
        reranked = self._rerank(query, merged, k=rerank_k)
        results['reranked'] = reranked
        
        # Level 4: 知识图谱扩展 (如果启用)
        if self.config.get('knowledge_graph', {}).get('enabled'):
            kg_results = self._kg_search(query)
            # 合并结果
            reranked = self._merge_with_kg(reranked, kg_results)
        
        results['documents'] = reranked
        return results
    
    def _vector_search(self, query: str, k: int, 
                       filter: Optional[Dict] = None) -> List[Document]:
        """向量相似度搜索"""
        query_embedding = self._generate_embeddings([query])[0]
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=filter
        )
        
        documents = []
        if results['ids']:
            for i, doc_id in enumerate(results['ids'][0]):
                doc = Document(
                    id=doc_id,
                    content=results['documents'][0][i],
                    metadata=results['metadatas'][0][i] if results['metadatas'] else {},
                    distance=results['distances'][0][i] if results['distances'] else None
                )
                documents.append(doc)
        
        return documents
    
    def _bm25_search(self, query: str, k: int) -> List[Document]:
        """BM25 关键词搜索"""
        if not self.bm25 or not self.documents:
            return []
        
        query_tokens = self._tokenize(query)
        scores = self.bm25.get_scores(query_tokens)
        
        # 获取 Top-K
        top_indices = np.argsort(scores)[::-1][:k]
        
        documents = []
        for idx in top_indices:
            if scores[idx] > 0:
                doc = self.documents[idx]
                doc.metadata['bm25_score'] = float(scores[idx])
                documents.append(doc)
        
        return documents
    
    def _reciprocal_rank_fusion(self, vector_results: List[Document],
                                 bm25_results: List[Document],
                                 k: int = 60) -> List[Document]:
        """RRF 融合算法"""
        scores = {}
        doc_map = {}
        
        # 向量结果得分
        for rank, doc in enumerate(vector_results):
            scores[doc.id] = scores.get(doc.id, 0) + 1.0 / (k + rank + 1)
            doc_map[doc.id] = doc
        
        # BM25 结果得分
        for rank, doc in enumerate(bm25_results):
            scores[doc.id] = scores.get(doc.id, 0) + 1.0 / (k + rank + 1)
            doc_map[doc.id] = doc
        
        # 排序
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # 去重并返回
        seen = set()
        results = []
        for doc_id, score in sorted_ids:
            content_hash = hashlib.md5(doc_map[doc_id].content.encode()).hexdigest()[:16]
            if content_hash not in seen:
                seen.add(content_hash)
                doc = doc_map[doc_id]
                doc.metadata['rrf_score'] = score
                results.append(doc)
        
        return results
    
    def _rerank(self, query: str, documents: List[Document], 
                k: int) -> List[Document]:
        """使用重排序模型精排"""
        if len(documents) <= k:
            return documents
        
        try:
            # 使用 CrossEncoder 重排序
            from sentence_transformers import CrossEncoder
            model_name = self.config.get('retrieval', {}).get(
                'rerank_model', 'BAAI/bge-reranker-large'
            )
            model = CrossEncoder(model_name)
            
            pairs = [[query, doc.content] for doc in documents]
            scores = model.predict(pairs)
            
            # 排序
            scored_docs = list(zip(documents, scores))
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            
            results = []
            for doc, score in scored_docs[:k]:
                doc.metadata['rerank_score'] = float(score)
                results.append(doc)
            
            return results
            
        except Exception as e:
            print(f"重排序失败: {e}")
            return documents[:k]
    
    def _kg_search(self, query: str) -> List[Document]:
        """知识图谱搜索（预留）"""
        # TODO: 实现 Neo4j 知识图谱查询
        return []
    
    def _merge_with_kg(self, documents: List[Document], 
                       kg_results: List[Document]) -> List[Document]:
        """合并知识图谱结果"""
        # 简单合并，去重
        seen = {hashlib.md5(d.content.encode()).hexdigest()[:16] for d in documents}
        
        for doc in kg_results:
            content_hash = hashlib.md5(doc.content.encode()).hexdigest()[:16]
            if content_hash not in seen:
                documents.append(doc)
                seen.add(content_hash)
        
        return documents
    
    def format_context(self, results: Dict[str, Any]) -> str:
        """格式化检索结果为上下文"""
        documents = results.get('documents', [])
        
        if not documents:
            return ""
        
        context_parts = []
        for i, doc in enumerate(documents, 1):
            source = doc.metadata.get('source', '未知来源')
            score = doc.metadata.get('rerank_score', 0)
            
            context_parts.append(
                f"[{i}] 来源: {source} (相关度: {score:.3f})\n{doc.content}\n"
            )
        
        return "\n".join(context_parts)
    
    def document_count(self) -> int:
        """获取文档数量"""
        if self.collection:
            return self.collection.count()
        return 0
    
    def persist(self):
        """持久化向量库"""
        if self.vector_store:
            # Chroma 自动持久化
            pass
