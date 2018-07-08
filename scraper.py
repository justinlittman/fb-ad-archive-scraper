from time import sleep
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from PIL import Image
from io import BytesIO
from collections import deque
from urllib.parse import urlencode
from datetime import datetime
import os
import csv
import argparse
import json
import requests
from collections import OrderedDict
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities


def find_ad_class(driver):
    divs = deque([driver.find_element_by_id('content')])
    while divs:
        div = divs.popleft()
        if '1px solid rgb(233, 234, 235)' == div.value_of_css_property('border'):
            return div.get_attribute('class')
        divs.extend(div.find_elements_by_xpath('div'))
    return None


def find_topnav_div(driver):
    divs = deque([driver.find_element_by_id('content')])
    while divs:
        div = divs.popleft()
        if 'fixed' == div.value_of_css_property('position'):
            return div
        divs.extend(div.find_elements_by_xpath('div'))
    return None


def blank_ad():
    return {'ad_archive_id': None,
            'screenshot': None,
            'impressions': None,
            'spend': None,
            'start_date': None,
            'end_date': None,
            'creation_time': None,
            'is_active': None,
            'is_promoted_news': None,
            'page_id': None,
            'page_name': None,
            'snapshot_id': None,
            'html': None,
            'byline': None,
            'caption': None,
            'title': None,
            'link_description': None,
            'display_format': None,
            'instagram_actor_name': None,
            'page_like_count': None
            }


def process_ad_divs(ad_divs, ad_count, driver, dirname, ad_limit):
    # Add whitespace to bottom to allow scrolling to bottom row
    window_height = driver.execute_script('return window.innerHeight')
    driver.execute_script("arguments[0].setAttribute('style', 'margin-bottom:{}px;')".format(window_height),
                          ad_divs[-1])
    processed_add_divs = set()
    for ad_div in ad_divs:
        ad_count += 1
        print('Ad {}'.format(ad_count))
        screenshot(ad_div, ad_count, dirname, driver)
        processed_add_divs.add(ad_div)
        if ad_limit == ad_count:
            break

    return processed_add_divs


def class_to_css_selector(clazz):
    # This handles compound class names.
    return ".{}".format(clazz.replace(' ', '.'))


def screenshot(ad_div, ad_count, dirname, driver):
    window_height = driver.execute_script('return window.innerHeight')
    ad_top = ad_div.location['y']
    ad_height = ad_div.size['height']
    ad_bottom = ad_top + ad_height
    ad_left = ad_div.location['x']
    ad_right = ad_left + ad_div.size['width']

    offset = ad_top
    slices = []
    img_height = 0
    while offset < ad_bottom:
        driver.execute_script("window.scrollTo(0, %s);" % offset)
        img = Image.open(BytesIO(driver.get_screenshot_as_png()))
        img_height += img.size[1]
        slices.append(img)
        offset += window_height

    screenshot_img = Image.new('RGB', (slices[0].size[0], img_height))
    offset = 0
    for img in slices:
        screenshot_img.paste(img, (0, offset))
        offset += img.size[1]

    screenshot_img.crop((ad_left * 2, 0, ad_right * 2, ad_height * 2)).save('{}/ad-{:04}.png'.format(dirname, ad_count))


def write_readme(dirname, timestamp, q, limit):
    with open('{}/README.txt'.format(dirname), 'w') as readme:
        readme.write('Scrape of Facebook Archive of Ads with Political Content\n')
        readme.write('Performed by fb-ad-archive-scraper (https://github.com/justinlittman/fb-ad-archive-scraper).\n\n')
        readme.write('Query: {}\n'.format(q))
        readme.write('Started: {}\n'.format(timestamp.isoformat()))
        if limit:
            readme.write('Limit: {}'.format(limit))


def main(q, fb_email, fb_password, ad_limit=None, headless=True):
    timestamp = datetime.now()
    # Create directory
    dirname = '{}-{}'.format(q.replace(' ', '_'), timestamp.strftime('%Y%m%d%H%M%S'))
    os.makedirs(dirname)
    write_readme(dirname, timestamp, q, ad_limit)

    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('headless')

    caps = DesiredCapabilities.CHROME
    caps['loggingPrefs'] = {'performance': 'ALL'}

    driver = webdriver.Chrome(options=options, desired_capabilities=caps)
    driver.implicitly_wait(10)
    try:
        print('Logging into Facebook')
        driver.get(
            'https://www.facebook.com/politicalcontentads/?{}'.format(urlencode({'active_status': 'all', 'q': q})))
        driver.find_element_by_name('email').send_keys(fb_email)
        driver.find_element_by_name('pass').send_keys(fb_password)
        driver.find_element_by_name('login').click()
        sleep(5)

        try:
            driver.find_element_by_id('loginbutton')
            print('Login failed')
            return
        except NoSuchElementException:
            print('Login succeeded')

        # Has results
        try:
            driver.find_element_by_xpath('//div[contains(text(),"There are no ads matching")]')
            print('No results')
            return
        except NoSuchElementException:
            pass

        # Fix topnav for screenshots
        print('Finding and fixing top nav')
        topnav_div = find_topnav_div(driver)
        assert topnav_div
        driver.execute_script("arguments[0].setAttribute('style', 'position: absolute; top: 0px;')", topnav_div)

        # Find the ad class
        print('Finding ad class')
        ad_clazz = find_ad_class(driver)
        assert ad_clazz

        page = 1
        processed_ad_divs = set()
        new_ad_divs = driver.find_elements_by_css_selector(class_to_css_selector(ad_clazz))
        while new_ad_divs and (ad_limit is None or ad_limit > len(processed_ad_divs)):
            print("Processing {} ads on page {}".format(len(new_ad_divs), page))
            processed_ad_divs.update(
                process_ad_divs(new_ad_divs, len(processed_ad_divs), driver, dirname, ad_limit))
            sleep(1)
            all_ad_divs = driver.find_elements_by_css_selector(class_to_css_selector(ad_clazz))
            new_ad_divs = [ad_div for ad_div in all_ad_divs if ad_div not in processed_ad_divs]
            page += 1

        print('Fetching XHRs')
        jar = requests.cookies.RequestsCookieJar()
        for cookie in driver.get_cookies():
            jar.set(cookie['name'], cookie['value'], domain=cookie['domain'], path=cookie['path'])

        ads_performance_logs = []
        ads_creative_logs = []
        for entry in driver.get_log('performance'):
            msg = json.loads(entry['message'])

            if msg.get('message', {}).get('method', {}) == 'Network.requestWillBeSent':
                url = msg['message']['params']['request']['url']
                # print(url)
                if url.startswith('https://www.facebook.com/politicalcontentads/ads/'):
                    ads_performance_logs.append(msg)
                elif url.startswith('https://www.facebook.com/ads/political_ad_archive/creative_snapshot/'):
                    ads_creative_logs.append(msg)

        ads = OrderedDict()

        # Ads performance
        for page, msg in enumerate(ads_performance_logs):
            r = requests.post(msg['message']['params']['request']['url'],
                              headers=msg['message']['params']['request']['headers'],
                              data=msg['message']['params']['request']['postData'],
                              cookies=jar)
            r.raise_for_status()
            payload = json.loads(r.text[9:])
            with open('{}/ads-performance-{:04}.json'.format(dirname, page+1), 'w') as file:
                json.dump(payload['payload'], file, indent=2)
            for ad_performance in payload['payload']['results']:
                ad = blank_ad()
                ad['ad_archive_id'] = ad_performance['adArchiveID']
                ad['impressions'] = ad_performance['adInsightsInfo']['impressions']
                ad['spend'] = ad_performance['adInsightsInfo']['spend'].replace('\u003C', '<')
                ad['is_active'] = ad_performance['isActive']
                ad['is_promoted_news'] = ad_performance['isPromotedNews']
                ad['snapshot_id'] = ad_performance['snapshotID']
                ad['start_date'] = datetime.fromtimestamp(ad_performance['startDate']).isoformat()
                if ad['end_date']:
                    ad['end_date'] = datetime.fromtimestamp(ad_performance['endDate']).isoformat()
                ads[ad_performance['adArchiveID']] = ad

        # Ads creative
        for page, msg in enumerate(ads_creative_logs):
            r = requests.post(msg['message']['params']['request']['url'],
                              headers=msg['message']['params']['request']['headers'],
                              data=msg['message']['params']['request']['postData'],
                              cookies=jar)
            r.raise_for_status()
            payload = json.loads(r.text[9:])
            for ad_archive_id, ad_creative in payload['payload'].items():
                ad = ads[ad_archive_id]
                ad['page_name'] = ad_creative['fields']['page_name']
                ad['page_id'] = ad_creative['fields']['page_id']
                ad['html'] = ad_creative['fields']['body']['markup']['__html']
                ad['byline'] = ad_creative['fields']['byline']
                ad['caption'] = ad_creative['fields']['caption']
                ad['title'] = ad_creative['fields']['title']
                ad['link_description'] = ad_creative['fields']['link_description']
                ad['display_format'] = ad_creative['fields']['display_format']
                ad['instagram_actor_name'] = ad_creative['fields']['instagram_actor_name']
                ad['page_like_count'] = ad_creative['fields']['page_like_count']
                ad['creation_time'] = datetime.fromtimestamp(ad_creative['fields']['creation_time']).isoformat()

            with open('{}/ads-creative-{:04}.json'.format(dirname, page+1), 'w') as file:
                json.dump(payload['payload'], file, indent=2)

        # Add screenshot
        for count, ad in enumerate(ads.values()):
            ad['screenshot'] = 'ad-{:04}.png'.format(count + 1)

        with open('{}/ads.csv'.format(dirname), 'w') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=blank_ad().keys())
            writer.writeheader()
            writer.writerows(list(ads.values())[:(ad_limit or len(ads))])

    finally:
        driver.close()
        driver.quit()

    print('Done')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scrape Facebook\'s Archive of Ads with Political Content')
    parser.add_argument('email', help='Email address for FB account')
    parser.add_argument('password', help='Password for FB account')
    parser.add_argument('query', help='Query', nargs='+')
    parser.add_argument('--limit', help='Limit on number of ads to scrape', type=int)
    parser.add_argument('--headed', help='Use a headed chrome browser', action='store_true')

    args = parser.parse_args()
    main(' '.join(args.query), args.email, args.password, ad_limit=args.limit, headless=not args.headed)
