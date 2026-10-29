from testkart_intelligence.discovery.fetcher import SafeFetcher

fetcher = SafeFetcher()
url = "https://ssc.gov.in/api/general-website/portal/notice-boards?page=1&limit=5&contentType=notice-boards&key=createdAt&order=DESC&isAttachment=true&language=english&attributes=id,headline,examId,contentType,redirectUrl,startDate,endDate,language,createdAt"

try:
    content, ctype, status, final_url = fetcher.fetch(url)
    print("Status:", status)
    print("Content len:", len(content))
    print("Snippet:", content[:200])
except Exception as e:
    print("Fetch error:", e)
