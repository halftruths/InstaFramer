from playwright.sync_api import sync_playwright
import time
import os
import requests
import uuid
import zipfile

CACHE_DIR = "amazon_cache"

def clear_amazon_cache():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
        return
        
    for filename in os.listdir(CACHE_DIR):
        file_path = os.path.join(CACHE_DIR, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")

def get_amazon_photos(share_url: str):
    print(f"Fetching Amazon Photos from: {share_url}")
    
    download_urls = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            accept_downloads=True
        )
        page = context.new_page()
        
        def on_download(download):
            print(f"Intercepted verified download URL: {download.url}")
            download_urls.add(download.url)
            download.cancel()
            
        page.on("download", on_download)

        print("Waiting for page and DOM to render...")
        try:
            page.goto(share_url, wait_until="networkidle", timeout=30000)
            # Amazon has heavily delayed JS rendering, so we poll the DOM for up to 20 seconds
            download_triggered = False
            items = []
            
            print("Polling for Download button or grid items...")
            for attempt in range(20):
                page.wait_for_timeout(1000)
                # Amazon sometimes hides the Download button inside a 'toggle' menu
                try:
                    toggle = page.locator("button.toggle").first
                    if toggle and toggle.is_visible(timeout=1000):
                        print("Clicking hidden '.toggle' menu button...")
                        toggle.click()
                        page.wait_for_timeout(500)
                except Exception as e:
                    pass

                # Try finding a global download button immediately available or in the menu
                top_buttons = page.locator("button, a, li").all()
                for b in top_buttons:
                    if b.is_visible() and b.text_content() and "download" in b.text_content().lower():
                        print(f"Found immediate top-level 'Download' button on attempt {attempt}.")
                        try:
                            with page.expect_download(timeout=10000) as download_info:
                                b.click()
                            download_urls.add(download_info.value.url)
                            download_triggered = True
                            break
                        except Exception as e:
                            print(f"Failed to trigger global download: {e}")
                            
                if download_triggered:
                    break
                    
                # Try finding grid items if download wasn't triggered
                items = page.locator(".react-photo-grid-item, div.node-image, li").all()
                if len(items) > 0:
                    visible_items = [item for item in items if item.is_visible()]
                    if len(visible_items) > 0:
                        print(f"Discovered {len(visible_items)} visible grid items on attempt {attempt}.")
                        items = visible_items
                        break
                        
            # If no immediate download button worked, we fall back to grid interaction
            if not download_triggered and len(items) > 0:
                print(f"Processing {len(items)} grid items via hover simulation...")
                for index, item in enumerate(items):
                    item.hover()
                    page.wait_for_timeout(500)
                    
                    # Check for the checkbox or selection div that appears on hover
                    buttons = item.locator("button, div[role='checkbox']").all()
                    for btn in buttons:
                        if btn.is_visible():
                            try:
                                btn.click()
                                page.wait_for_timeout(300)
                                break # Move to next item once selected
                            except:
                                pass
                                
                # Now trigger the global download button that should have appeared
                header_buttons = page.locator("button").all()
                for b in header_buttons:
                    if b.is_visible() and "download" in b.text_content().lower():
                        print("Clicking top-level 'Download' bar...")
                        try:
                            with page.expect_download(timeout=10000) as download_info:
                                b.click()
                            download_urls.add(download_info.value.url)
                        except Exception as e:
                            print(f"Could not trigger download: {e}")
                            
            if not download_triggered and len(download_urls) == 0:
                print("No downloads triggered, taking screenshot to debug...")
                page.screenshot(path="research/headless_fail.png")

        except Exception as e:
            print(f"Error navigating or scanning UI: {e}")
            
        browser.close()
        
    print(f"Gathered {len(download_urls)} download streams.")
    
    # Now, stream them to the cache
    clear_amazon_cache()
    
    downloaded_files = []
    
    for idx, url in enumerate(download_urls):
        try:
            res = requests.get(url, stream=True)
            res.raise_for_status()
            
            # Predict extension (if impossible to parse from headers, use jpg)
            ext = ".jpg" 
            content_disp = res.headers.get("Content-Disposition", "")
            if "filename=" in content_disp:
                parsed_filename = content_disp.split("filename=")[-1].strip('"\'')
                _, parsed_ext = os.path.splitext(parsed_filename)
                if parsed_ext: ext = parsed_ext
            
            outfile = os.path.join(CACHE_DIR, f"amazon_img_{idx:03d}{ext}")
            with open(outfile, 'wb') as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            downloaded_files.append(outfile)
            print(f"Saved {outfile}")
            
            # If it's a zip file, extract it and remove the archive
            if ext.lower() == ".zip":
                print(f"Extracting ZIP archive: {outfile}")
                with zipfile.ZipFile(outfile, 'r') as zip_ref:
                    zip_ref.extractall(CACHE_DIR)
                os.remove(outfile)
                
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            
    return os.path.abspath(CACHE_DIR)

if __name__ == "__main__":
    # Test
    out = get_amazon_photos("https://www.amazon.com/photos/shared/9DohP4MpQu2KLsJDjHXzIw.Hv5UUX9Ib9u2HkwIjaeLZs")
    print(f"Success. Files saved in: {out}")
