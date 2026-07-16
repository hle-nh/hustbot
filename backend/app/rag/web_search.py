import logging
import urllib.request
import urllib.parse
import re
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

def web_search(query: str, max_results: int = 4) -> list[Document]:
    """
    Tìm kiếm thông tin từ web bằng DuckDuckGo Lite Scraper (Regex-based).
    Phương pháp này không cần API key, hoàn toàn miễn phí và cực kỳ ổn định.
    """
    search_query = query
    if "hust" not in query.lower() and "bách khoa" not in query.lower():
        search_query = f"{query} HUST Bách Khoa"

    logger.info(f"Đang thực hiện Web Search Fallback cho query: {search_query}")

    try:
        url = "https://lite.duckduckgo.com/lite/"
        data = urllib.parse.urlencode({"q": search_query}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode("utf-8", errors="ignore")

        # Parse links: <a rel="nofollow" href="..." class='result-link'>...</a>
        link_pattern = r'<a[^>]+href="([^"]+)"[^>]*class=[\x27\x22]result-link[\x27\x22][^>]*>(.*?)</a>'
        links = re.findall(link_pattern, html, re.DOTALL)

        # Parse snippets: <td class='result-snippet'>...</td>
        snippet_pattern = r'<td[^>]+class=[\x27\x22]result-snippet[\x27\x22][^>]*>(.*?)</td>'
        snippets = re.findall(snippet_pattern, html, re.DOTALL)

        docs = []
        for i, ((href, title), snippet) in enumerate(zip(links, snippets)):
            if len(docs) >= max_results:
                break

            title = re.sub(r'<[^>]+>', '', title).strip()
            snippet = re.sub(r'<[^>]+>', '', snippet).strip()

            if "uddg=" in href:
                href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])

            content = f"[Nguồn Web: {title} | Link: {href}]\n{snippet}"

            docs.append(Document(
                page_content=content,
                metadata={
                    "source": href,
                    "page": f"Web Result #{i+1}",
                    "title": title
                }
            ))

        logger.info(f"Web Search thành công: Tìm thấy {len(docs)} kết quả.")
        return docs

    except Exception as e:
        logger.error(f"Lỗi khi thực hiện DuckDuckGo Web Search: {str(e)}")
        return []
