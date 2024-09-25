import json
import os
import httpx
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class LocalStorage:
    def __init__(self, base_path):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

    async def store_book_info(self, book_id, book_info):
        with open(os.path.join(self.base_path, f"book_{book_id}.json"), 'w', encoding='utf-8') as f:
            json.dump(book_info, f, ensure_ascii=False, indent=2)

    async def get_book_info(self, book_id):
        try:
            with open(os.path.join(self.base_path, f"book_{book_id}.json"), 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    async def store_section_content(self, section_id, content):
        with open(os.path.join(self.base_path, f"section_{section_id}.md"), 'w', encoding='utf-8') as f:
            f.write(content)

    async def get_section_content(self, section_id):
        try:
            with open(os.path.join(self.base_path, f"section_{section_id}.md"), 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return None

    async def list_all_books(self):
        return [f.split('_')[1].split('.')[0] for f in os.listdir(self.base_path) if f.startswith('book_')]

    async def delete_book(self, book_id):
        os.remove(os.path.join(self.base_path, f"book_{book_id}.json"))

    async def delete_section(self, section_id):
        os.remove(os.path.join(self.base_path, f"section_{section_id}.md"))

class VercelKVStorage:
    def __init__(self, kv_rest_api_url: str, kv_rest_api_token: str):
        self.base_url = kv_rest_api_url
        self.headers = {
            "Authorization": f"Bearer {kv_rest_api_token}",
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient(headers=self.headers)

    async def store_book_info(self, book_id: str, book_info: Dict[str, Any]) -> None:
        url = f"{self.base_url}/set/book_{book_id}"
        try:
            response = await self.client.post(url, json=book_info)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"存储小册信息到 Vercel KV 失败: {e}")

    async def get_book_info(self, book_id: str) -> Dict[str, Any] | None:
        url = f"{self.base_url}/get/book_{book_id}"
        response = await self.client.get(url)
        if response.status_code == 200:
            return response.json()
        return None

    async def store_section_content(self, section_id: str, content: str) -> None:
        url = f"{self.base_url}/set/section_{section_id}"
        await self.client.post(url, json=content)

    async def get_section_content(self, section_id: str) -> str | None:
        url = f"{self.base_url}/get/section_{section_id}"
        response = await self.client.get(url)
        if response.status_code == 200:
            return response.text
        return None

    async def list_all_books(self) -> List[str]:
        url = f"{self.base_url}/keys/book_*"
        response = await self.client.get(url)
        if response.status_code == 200:
            keys = response.json()
            return [key.split('_')[1] for key in keys]
        return []

    async def delete_book(self, book_id: str) -> None:
        url = f"{self.base_url}/del/book_{book_id}"
        await self.client.post(url)

    async def delete_section(self, section_id: str) -> None:
        url = f"{self.base_url}/del/section_{section_id}"
        await self.client.post(url)

    async def close(self) -> None:
        await self.client.aclose()

class StoragePlugin:
    def __init__(self, config: Dict[str, Any]):
        self.use_vercel = config.get('use_vercel', False)
        self.write_to_vercel = config.get('write_to_vercel', False)
        
        if self.use_vercel:
            kv_rest_api_url = os.environ.get('VERCEL_KV_REST_API_URL') or config['vercel'].get('kv_rest_api_url')
            kv_rest_api_token = os.environ.get('VERCEL_KV_REST_API_TOKEN') or config['vercel'].get('kv_rest_api_token')
            
            if not kv_rest_api_url or not kv_rest_api_token:
                logger.warning("Vercel KV 配置不完整，将仅使用本地存储")
                self.use_vercel = False
                self.write_to_vercel = False
            else:
                try:
                    self.vercel_storage = VercelKVStorage(kv_rest_api_url, kv_rest_api_token)
                except Exception as e:
                    logger.error(f"初始化 Vercel KV 存储失败: {e}")
                    self.use_vercel = False
                    self.write_to_vercel = False
        
        local_storage_path = os.environ.get('LOCAL_STORAGE_PATH') or config.get('local_storage_path', './data')
        self.local_storage = LocalStorage(local_storage_path)

    async def store_book_info(self, book_id: str, book_info: Dict[str, Any]) -> None:
        try:
            await self.local_storage.store_book_info(book_id, book_info)
        except Exception as e:
            logger.error(f"存储小册信息到本地失败: {e}")
        
        if self.use_vercel and self.write_to_vercel:
            try:
                await self.vercel_storage.store_book_info(book_id, book_info)
            except Exception as e:
                logger.error(f"存储小册信息到 Vercel KV 失败: {e}")

    async def get_book_info(self, book_id: str) -> Dict[str, Any] | None:
        if self.use_vercel:
            try:
                vercel_info = await self.vercel_storage.get_book_info(book_id)
                if vercel_info:
                    return vercel_info
            except Exception as e:
                logger.error(f"从 Vercel KV 获取小册信息失败: {e}")
        
        try:
            return await self.local_storage.get_book_info(book_id)
        except Exception as e:
            logger.error(f"从本地存储获取小册信息失败: {e}")
            return None

    async def store_section_content(self, section_id: str, content: str) -> None:
        await self.local_storage.store_section_content(section_id, content)
        if self.use_vercel and self.write_to_vercel:
            await self.vercel_storage.store_section_content(section_id, content)

    async def get_section_content(self, section_id: str) -> str | None:
        if self.use_vercel:
            vercel_content = await self.vercel_storage.get_section_content(section_id)
            if vercel_content:
                return vercel_content
        return await self.local_storage.get_section_content(section_id)

    async def list_all_books(self) -> List[str]:
        if self.use_vercel:
            return await self.vercel_storage.list_all_books()
        return await self.local_storage.list_all_books()

    async def delete_book(self, book_id: str) -> None:
        await self.local_storage.delete_book(book_id)
        if self.use_vercel:
            await self.vercel_storage.delete_book(book_id)

    async def delete_section(self, section_id: str) -> None:
        await self.local_storage.delete_section(section_id)
        if self.use_vercel:
            await self.vercel_storage.delete_section(section_id)

    async def close(self) -> None:
        if self.use_vercel:
            try:
                await self.vercel_storage.close()
            except Exception as e:
                logger.error(f"关闭 Vercel KV 存储连接失败: {e}")
