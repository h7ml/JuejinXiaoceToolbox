import logging
import os
import re
import traceback
import yaml
import httpx
import asyncio
import random
from tqdm import tqdm
from typing import List, Dict, Any
from plugins.storage_plugin import StoragePlugin
from datetime import datetime
from utils.config import load_config
import json
import shutil
import markdown
import zipfile

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
error_logger = logging.getLogger('error')
all_logger = logging.getLogger('all')

def makedirs(path: str) -> None:
    """创建目录，如果目录不存在"""
    if not os.path.exists(path):
        os.makedirs(path)

def clear_slash(s: str) -> str:
    """清除字符串中的斜杠和竖线"""
    return s.replace('\\', '').replace('/', '').replace('|', '')

class Juejinxiaoce2Markdown:
    img_pattern = re.compile(r'!\[.*?\]\((.*?)\)', re.S)

    def __init__(self, config: Dict[str, Any], progress_callback=None, log_callback=None, detailed_log_callback=None, book_progress_callback=None, section_progress_callback=None):
        self.config = config
        self.cookie = config.get('cookie', '')
        self.save_dir = config.get('save_dir', './output')
        self.fetch_book_ids_online = config.get('fetch_book_ids_online', False)
        self.overwrite_existing = config.get('overwrite_existing', False)
        self.save_images_locally = config.get('save_images_locally', False)
        self.book_ids = config.get('book_ids', [])
        self.single_book_mode = len(self.book_ids) == 1
        self.should_clear_log_folder = config.get('should_clear_log_folder', False)
        self.resume_download = config.get('resume_download', False)
        self.save_format = config.get('save_format', 'markdown')
        self.compress_to_zip = config.get('compress_to_zip', False)

        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.detailed_log_callback = detailed_log_callback
        self.book_progress_callback = book_progress_callback
        self.section_progress_callback = section_progress_callback

        self.base_url = "https://juejin.cn/book/"
        self.client = None
        self.total_books = len(self.book_ids)
        self.processed_books = 0
        self.download_progress = {}
        self.progress_file = os.path.join(self.save_dir, 'download_progress.json')

        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

        self.storage = StoragePlugin(config.get('storage', {}))

        if self.resume_download:
            self.download_progress = self.load_progress()

        self.validate_config()

    def validate_config(self):
        if not self.cookie:
            raise ValueError("Cookie 不能为空")
        if not self.save_dir:
            raise ValueError("保存目录不能为空")
        if not self.fetch_book_ids_online and not self.book_ids:
            raise ValueError("未指定要下载的小册 ID，且未启用在线获取小册列表")

    def get_headers(self):
        return {
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9',
            'content-type': 'application/json',
            'cookie': self.cookie.strip(),
            'origin': 'https://juejin.cn',
            'referer': 'https://juejin.cn/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }

    async def is_cookie_valid(self) -> bool:
        self.detailed_log("正在验证 Cookie 有效性...")
        url = "https://api.juejin.cn/user_api/v1/user/get"
        params = {
            "aid": "2608",
            "uuid": "7390948006004852278",
            "spider": "0",
            "not_self": "0"
        }
        headers = self.get_headers()
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.get(url, params=params, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("err_no") == 0 and data.get("err_msg") == "success":
                        user_data = data.get("data")
                        if user_data and isinstance(user_data, dict):
                            self.log_message("Cookie 有效")
                            return True
                
                self.log_message(f"Cookie 可能无效,响应内容: {data}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
            except Exception as e:
                self.log_message(f"检查 cookie 时发生错误: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
        
        self.save_curl_command(url, params, headers)
        return False

    def save_curl_command(self, url: str, params: dict, headers: dict, data: dict = None):
        log_dir = '.log'
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(log_dir, f'curl_command_{timestamp}.curl')
        
        full_url = f"{url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
        
        curl_command = f"curl '{full_url}' \\\n"
        for key, value in headers.items():
            curl_command += f"  -H '{key}: {value}' \\\n"
        curl_command += f"  -H 'cookie: {self.cookie}'"
        
        if data:
            curl_command += f" \\\n  -d '{json.dumps(data)}'"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(curl_command)
        
        self.log_message(f"已将 cURL 命令保存至: {file_path}")

    async def fetch_book_ids(self):
        self.detailed_log("开始获取在线小册列表...")
        url = 'https://api.juejin.cn/booklet_api/v1/booklet/bookletshelflist'
        params = {
            'aid': '2608',
            'uuid': '7390948006004852278',
            'spider': '0'
        }
        data = {
            'cursor': '0',
            'limit': 100,
            'sort': 0
        }
        
        try:
            response = await self.client.post(url, params=params, json=data)
            response.raise_for_status()
            result = response.json()
            
            if result['err_no'] == 0:
                book_ids = [item['booklet_id'] for item in result['data']]
                self.book_ids = book_ids
                self.total_books = len(book_ids)
                self.log_message(f"成功获取到 {self.total_books} 本小册")
            else:
                self.log_message(f"获取小册列表失败: {result['err_msg']}")
                self.save_curl_command(url, params, self.get_headers(), data)
        except Exception as e:
            self.log_message(f"获取小册列表时发生错误: {str(e)}")
            self.save_curl_command(url, params, self.get_headers(), data)

    async def get_book_info_res(self, book_id: str):
        url = 'https://api.juejin.cn/booklet_api/v1/booklet/get'
        params = {
            'aid': '2608',
            'uuid': '7390948006004852278',
            'spider': '0'
        }
        data = {
            'booklet_id': str(book_id)
        }
        
        headers = self.get_headers()

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.post(url, params=params, json=data, headers=headers)
                response.raise_for_status()
                result = response.json()
                await asyncio.sleep(random.uniform(2, 5))
                return result
            except httpx.HTTPError as e:
                self.log_message(f"获取小册信息失败，正在进行第{attempt + 1}次重试: {e}")
                if attempt == max_retries - 1:
                    self.log_message(f"获取小册信息失败，已达到最大重试次数: {e}")
                    self.save_curl_command(url, params, headers, data)
                    return None
            await asyncio.sleep(random.uniform(5, 10))

        return None

    async def get_section_content(self, section_id: str) -> str:
        url = 'https://api.juejin.cn/booklet_api/v1/section/get'
        params = {
            'aid': '2608',
            'uuid': '7390948006004852278',
            'spider': '0'
        }
        data = {
            'section_id': section_id
        }
        
        try:
            response = await self.client.post(url, params=params, json=data)
            response.raise_for_status()
            result = response.json()
            
            if result['err_no'] == 0:
                return result['data']['section']['markdown_show']
            else:
                self.log_message(f"获取章节内容失败: {result['err_msg']}")
                self.save_curl_command(url, params, self.get_headers(), data)
                return ""
        except Exception as e:
            self.log_message(f"获取章节内容时发生错误: {str(e)}")
            self.save_curl_command(url, params, self.get_headers(), data)
            return ""

    async def download_image(self, img_url: str, save_path: str) -> bool:
        self.detailed_log(f"下载图片: {img_url}")
        try:
            async with self.client.get(img_url) as response:
                if response.status_code == 200:
                    content = await response.read()
                    with open(save_path, 'wb') as f:
                        f.write(content)
                    return True
                else:
                    self.log_message(f"下载图片失败: {img_url}, 状态码: {response.status_code}")
                    return False
        except Exception as e:
            self.log_message(f"下载图片时发生错误: {img_url}, 错误: {str(e)}")
            return False

    async def save_content(self, file_path: str, content: str):
        base_path, _ = os.path.splitext(file_path)
        if self.save_format == 'markdown':
            await self.save_markdown(file_path, content)
        elif self.save_format == 'html':
            await self.save_html(f"{base_path}.html", content)

    async def save_markdown(self, file_path: str, content: str):
        """保存markdown文件并处理图片"""
        self.detailed_log(f"尝试保存 Markdown 文件: {file_path}")
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            img_urls = re.findall(self.img_pattern, content)
            for img_index, img_url in enumerate(img_urls):
                new_img_url: str = img_url.replace('\n', '')
                if self.save_images_locally:
                    try:
                        suffix = os.path.splitext(new_img_url)[-1]
                        img_file_name = f'{img_index + 1}{suffix}'.replace('?', '')
                        md_relative_img_path = os.path.join(markdown_relative_img_dir, img_file_name)
                        img_save_path = os.path.join(section_img_dir, img_file_name)
                        
                        if await self.download_image(new_img_url, img_save_path):
                            content = content.replace(img_url, md_relative_img_path)
                        else:
                            self.log_message(f"图片下载失败，使用原链接: {new_img_url}")
                    except Exception as e:
                        error_msg = {
                            'msg': '处理图片失败',
                            'img_url': new_img_url,
                            'e': repr(e),
                            'traceback': traceback.format_exc(),
                            'markdown_relative_img_dir': markdown_relative_img_dir
                        }
                        self.log_message(error_msg)
                        error_logger.error(error_msg)
                        all_logger.error(error_msg)
                else:
                    # 如果不保存图片到本地，直接使用原有链接
                    content = content.replace(img_url, new_img_url)
            
            with open(file_path, 'w', encoding='utf8') as f:
                f.write(content)
            self.detailed_log(f"成功保存 Markdown 文件: {file_path}")
        except Exception as e:
            error_msg = f"保存 Markdown 文件时发生错误: {file_path}, 错误: {str(e)}"
            self.log_message(error_msg)
            self.detailed_log(error_msg)
            error_logger.error(error_msg)
            all_logger.error(error_msg)
            raise  # 重新抛出异常，以便上层函数可以捕获并处理

    async def save_html(self, file_path: str, content: str):
        html = markdown.markdown(content)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)

    async def generate_book_index(self, book_save_path: str, book_data: Dict, book_url: str):
        self.detailed_log(f"生成小册索引: {book_save_path}")
        index_file = 'index.html' if self.save_format == 'html' else 'README.md'
        index_path = os.path.join(book_save_path, index_file)
        
        content = f"# {book_data['booklet']['base_info']['title']}\n\n"
        content += f"作者: {book_data['booklet']['user_info']['user_name']}\n\n"
        content += f"小册地址: <a href='{book_url}' target='_blank'>{book_url}</a>\n\n"
        content += "## 目录\n\n"
        
        for index, section in enumerate(book_data['sections']):
            section_title = self.clear_filename(section['title'])
            file_extension = '.html' if self.save_format == 'html' else '.md'
            file_name = f"{index+1:03d}_{section_title}{file_extension}"
            content += f"{index+1}. <a href='{file_name}'>{section_title}</a>\n"
        
        if self.save_format == 'html':
            await self.save_html(index_path, content)
        else:
            await self.save_markdown(index_path, content)

    async def generate_main_index(self) -> None:
        """生成主目录的索引文件"""
        self.detailed_log("开始生成主索引文件")
        index_file = 'index.html' if self.save_format == 'html' else 'README.md'
        index_path = os.path.join(self.save_dir, index_file)
        self.detailed_log(f"索引文件路径: {index_path}")
        
        content = "# 掘金小册列表\n\n"
        existing_books = set()
        
        # 如果文件已存在，读取现有内容
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
                for line in existing_content.split('\n'):
                    if line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
                        book_id = line.split('/')[-1].split(')')[0]
                        existing_books.add(book_id)
                content = existing_content

        for index, book_id in enumerate(self.book_ids):
            if book_id in existing_books:
                self.detailed_log(f"小册 {book_id} 已存在于索引中，跳过")
                continue

            try:
                book_info = await self.get_book_info_res(book_id)
                
                if book_info is None or 'data' not in book_info or not book_info['data']:
                    content += f"{len(existing_books) + 1}. <a href='{self.base_url}{book_id}'>获取失败的小册 (ID: {book_id})</a>\n"
                    continue
                
                book_title = clear_slash(book_info['data']['booklet']['base_info']['title'])
                book_dir = f"{len(existing_books) + 1:03d}_{self.clear_filename(book_title)}"
                book_url = f"{self.base_url}{book_id}"
                book_index = 'index.html' if self.save_format == 'html' else 'README.md'
                content += f"{len(existing_books) + 1}. <a href='{book_dir}/{book_index}'>{book_title}</a> - <a href='{book_url}' target='_blank'>原文地址</a>\n"
                existing_books.add(book_id)
            except Exception as e:
                self.log_message(f"生成主索引时处理小册 {book_id} 出错: {str(e)}")
                content += f"{len(existing_books) + 1}. <a href='{self.base_url}{book_id}'>处理失败的小册 (ID: {book_id})</a>\n"
        
        if self.save_format == 'html':
            self.detailed_log("保存为 HTML 格式")
            await self.save_html(index_path, content)
        else:
            self.detailed_log("保存为 Markdown 格式")
            await self.save_markdown(index_path, content)
    
        self.detailed_log(f"主索引文件生成完成: {index_path}")

    def clear_log_folder(self):
        log_dir = '.log'
        if os.path.exists(log_dir):
            for filename in os.listdir(log_dir):
                file_path = os.path.join(log_dir, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    self.log_message(f'清除日志文件时发生错误: {e}')
        self.log_message('已尝试清除 .log 文件夹')

    @staticmethod
    def clear_filename(filename: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "", filename)

    def save_progress(self):
        progress = {
            'processed_books': self.processed_books,
            'book_progress': self.download_progress
        }
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

    def load_progress(self):
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                progress = json.load(f)
            self.processed_books = progress.get('processed_books', 0)
            return progress.get('book_progress', {})
        return {}

    async def process_book(self, book_id: str, index: int):
        try:
            self.detailed_log(f"开始处理小册 (ID: {book_id})")
            book_url = f"{self.base_url}{book_id}"
            self.log_message(f"处理小册 {index + 1}/{self.total_books}: {book_url}")

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.detailed_log(f"获取小册信息: {book_url}")
                    book_info = await self.get_book_info_res(book_id)
                    
                    if not book_info or 'data' not in book_info or not book_info['data']:
                        raise ValueError(f"小册 {book_id} 信息获取失败或为空")

                    book_title = book_info['data']['booklet']['base_info']['title']
                    self.detailed_log(f"小册标题: {book_title}")
                    book_save_path = os.path.join(self.save_dir, self.clear_filename(book_title))
                    makedirs(book_save_path)

                    sections = book_info['data']['sections']
                    await self.process_sections(sections, book_save_path, book_url, book_id)
                    await self.generate_book_index(book_save_path, book_info['data'], book_url)

                    self.processed_books += 1
                    self.log_message(f"小册 '{book_title}' 处理完成 ({self.processed_books}/{self.total_books})")
                    break
                except Exception as e:
                    error_msg = f"处理小册 '{book_id}' 时发生错误: {str(e)}"
                    self.log_message(error_msg)
                    self.detailed_log(error_msg)
                    error_logger.error(error_msg)
                    all_logger.error(error_msg)
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # 指数退避
                    else:
                        raise
        except Exception as e:
            error_msg = f"处理小册 '{book_id}' 时发生未知错误: {str(e)}"
            self.log_message(error_msg)
            self.detailed_log(error_msg)
            error_logger.error(error_msg)
            all_logger.error(error_msg)
            traceback.print_exc()

    async def process_sections(self, sections: List[Dict], book_save_path: str, book_url: str, book_id: str):
        self.detailed_log(f"开始处理小册章节，共 {len(sections)} 章")
        total_sections = len(sections)
        with tqdm(total=total_sections, desc="处理章节", ncols=100) as pbar:
            for index, section in enumerate(sections):
                try:
                    if book_id in self.download_progress and index < len(self.download_progress[book_id]['sections']):
                        self.log_message(f"跳过已下载的章节: {section['title']}")
                        self.detailed_log(f"跳过已下载的章节: {section['title']}")
                        pbar.update(1)
                        continue

                    self.detailed_log(f"处理章节 {index+1}/{len(sections)}: {section['title']}")
                    section_content = await self.get_section_content(section['section_id'])
                    section_title = self.clear_filename(section['title'])
                    file_name = f"{index+1:03d}_{section_title}.md"
                    file_path = os.path.join(book_save_path, file_name)
                    
                    # 如果需要保存图片到本地，创建图片目录
                    section_img_dir = os.path.join(book_save_path, f"{index+1:03d}_{section_title}_images") if self.save_images_locally else ""
                    markdown_relative_img_dir = f"{index+1:03d}_{section_title}_images" if self.save_images_locally else ""
                    
                    if self.save_images_locally:
                        os.makedirs(section_img_dir, exist_ok=True)
                    
                    await self.save_content(file_path, section_content)
                    
                    if book_id not in self.download_progress:
                        self.download_progress[book_id] = {'sections': []}
                    self.download_progress[book_id]['sections'].append(section['section_id'])
                    self.save_progress()
                    
                    pbar.update(1)
                    pbar.set_postfix_str(f"已保存: {section_title}")
                    if self.section_progress_callback:
                        self.section_progress_callback(index + 1, total_sections)
                except Exception as e:
                    self.log_message(f"  处理章节 '{section['title']}' 时发生错误: {str(e)}")
                    self.detailed_log(f"  处理章节 '{section['title']}' 时发生错误: {str(e)}")
                    pbar.update(1)
                    pbar.set_postfix_str(f"错误: {section['title']}")

    async def main(self, pause_check=None, cancel_check=None):
        self.detailed_log("开始主程序执行")
        try:
            if self.should_clear_log_folder:
                self.detailed_log("清理日志文件夹")
                self.clear_log_folder()

            async with httpx.AsyncClient(headers=self.get_headers(), timeout=30) as self.client:
                self.detailed_log("创建 HTTP 客户端")
                if not await self.is_cookie_valid():
                    self.detailed_log("Cookie 无效或已过期")
                    self.log_message("Cookie 无效或已过期，请更新配置文件中的 cookie")
                    return

                if self.fetch_book_ids_online and not self.single_book_mode:
                    self.detailed_log("开始在线获取小册列表")
                    await self.fetch_book_ids()
                elif not self.book_ids:
                    self.detailed_log("未指定要下载的小册 ID，且未启用在线获取小册列表")
                    self.log_message("未指定要下载的小册 ID，且未启用在线获取小册列表")
                    return
                
                self.detailed_log(f"开始处理，共有 {self.total_books} 个小册")
                self.log_message(f"开始处理，共有 {self.total_books} 个小册")
                if not self.book_ids:
                    self.detailed_log("没有找到要处理的小册")
                    self.log_message("没有找到要处理的小册，请检查配置或网络连接")
                    return

                for index, book_id in enumerate(self.book_ids):
                    if cancel_check and cancel_check():
                        self.detailed_log("下载已取消")
                        self.log_message("下载已取消")
                        self.save_progress()
                        return
                    if pause_check:
                        self.detailed_log("检查是否暂停")
                        await asyncio.to_thread(pause_check)
                    self.detailed_log(f"处理小册 {index+1}/{self.total_books}")
                    if self.book_progress_callback:
                        self.book_progress_callback(index + 1, self.total_books)
                    await self.process_book(book_id, index)
                    self.update_progress(int((index + 1) / self.total_books * 100))

                self.detailed_log("生成主索引文件")
                await self.generate_main_index()

                self.detailed_log(f"所有小册处理完成，共处理 {self.processed_books}/{self.total_books} 本")
                self.log_message(f"所有小册处理完成，共处理 {self.processed_books}/{self.total_books} 本")

                if self.compress_to_zip:
                    await self.compress_output()
        except Exception as e:
            self.detailed_log(f"发生错误: {str(e)}")
            self.log_message(f"发生错误: {str(e)}")
            traceback.print_exc()
        finally:
            self.save_progress()
            self.detailed_log("关闭存储插件")
            await self.storage.close()

    def update_progress(self, value):
        if self.progress_callback:
            self.progress_callback(value)

    def log_message(self, message):
        if self.log_callback:
            self.log_callback(message)
        logger.info(message)

    def detailed_log(self, message):
        if self.detailed_log_callback:
            self.detailed_log_callback(message)
        all_logger.debug(message)  # 使用 debug 级别记录详细日志

    async def compress_output(self):
        self.log_message("正在压缩下载的内容...")
        zip_filename = os.path.join(self.save_dir, "juejin_xiaoce_download.zip")
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(self.save_dir):
                for file in files:
                    if file != "juejin_xiaoce_download.zip":
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, self.save_dir)
                        zipf.write(file_path, arcname)
        self.log_message(f"压缩完成，文件保存在: {zip_filename}")

def run_from_command_line(config_path='config.yml'):
    # 使用 config_path 加载配置
    config = load_config(config_path)
    
    downloader = Juejinxiaoce2Markdown(config)
    asyncio.run(downloader.main())

if __name__ == '__main__':
    run_from_command_line()
