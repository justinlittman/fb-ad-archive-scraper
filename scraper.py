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
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.keys import Keys


def find_ad_class(driver):
    divs = deque([driver.find_element_by_id('content')])
    while divs:
        div = divs.popleft()
        if '1px solid rgb(233, 234, 235)' == div.value_of_css_property('border'):
            return div.get_attribute('class')
        divs.extend(div.find_elements_by_xpath('div'))
    return None


def find_topnav_divs(driver, count):
    divs = deque([driver.find_element_by_id('content')])
    topnav_divs = []
    while divs and len(topnav_divs) < count:
        div = divs.popleft()
        if 'fixed' == div.value_of_css_property('position'):
            topnav_divs.append(div)
        divs.extend(div.find_elements_by_xpath('div'))
    return topnav_divs


def blank_ad():
    return {'ad_archive_id': None,
            'screenshot': None,
            'performance': None,
            'impressions': None,
            'spend': None,
            'start_date': None,
            'end_date': None,
            'creation_time': None,
            'is_active': None,
            'is_promoted_news': None,
            'page_id': None,
            'page_name': None,
            'html': None,
            'byline': None,
            'caption': None,
            'title': None,
            'link_description': None,
            'display_format': None,
            'instagram_actor_name': None,
            'page_like_count': None
            }


def process_ad_divs(ad_divs, ad_count, driver, dirname, ad_limit, wait=0):
    # Add whitespace to bottom to allow scrolling to bottom row
    window_height = driver.execute_script('return window.innerHeight')
    driver.execute_script("arguments[0].setAttribute('style', 'margin-bottom:{}px;')".format(window_height),
                          ad_divs[-1])
    processed_add_divs = set()
    for ad_div in ad_divs:
        if ad_count > 0:
            sleep(wait)
        ad_count += 1
        print('Ad {}'.format(ad_count))
        screenshot(ad_div, ad_count, dirname, driver)
        # Click Ad Performance
        ad_div.find_element_by_link_text('See Ad Performance').click()
        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
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


def write_readme(dirname, timestamp, q, q_country, q_type, q_active_status, limit):
    with open('{}/README.txt'.format(dirname), 'w') as readme:
        readme.write('Scrape of Facebook Archive of Ads with Political Content\n')
        readme.write('Performed by fb-ad-archive-scraper (https://github.com/justinlittman/fb-ad-archive-scraper).\n\n')
        readme.write('Query: {}\n'.format(q))
        readme.write('Country: {}\n'.format(q_country))
        readme.write('Type: {}\n'.format(q_type))
        readme.write('Active status: {}\n'.format(q_active_status))
        readme.write('Started: {}\n'.format(timestamp.isoformat()))
        if limit:
            readme.write('Limit: {}'.format(limit))


def main(q, q_country, q_type, q_active_status, fb_email, fb_password, ad_limit=None, headless=True, wait=0):
    timestamp = datetime.now()
    # Create directory
    dirname = '{}-{}'.format(q.replace(' ', '_'), timestamp.strftime('%Y%m%d%H%M%S'))
    os.makedirs(dirname)
    write_readme(dirname, timestamp, q, q_country, q_type, q_active_status, ad_limit)

    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('headless')

    caps = DesiredCapabilities.CHROME
    caps['loggingPrefs'] = {'performance': 'ALL'}

    driver = webdriver.Chrome(options=options, desired_capabilities=caps)
    driver.implicitly_wait(10)
    try:
        print('Logging into Facebook')
        qs = {
            'active_status': q_active_status,
            'q': q,
            'country': q_country,
            'ad_type': q_type
        }
        driver.get(
            'https://www.facebook.com/politicalcontentads/?{}'.format(urlencode(qs)))
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
        print('Finding and fixing top navs')
        topnav_divs = find_topnav_divs(driver, 2)
        assert len(topnav_divs) == 2
        for topnav_div in topnav_divs:
            driver.execute_script("arguments[0].setAttribute('style', 'display: none;')", topnav_div)

        # Find the ad class
        print('Finding ad class')
        ad_clazz = find_ad_class(driver)
        assert ad_clazz
        # ad_clazz = '_2ivy __6e'

        page = 1
        processed_ad_divs = set()
        new_ad_divs = driver.find_elements_by_css_selector(class_to_css_selector(ad_clazz))
        while new_ad_divs and (ad_limit is None or ad_limit > len(processed_ad_divs)):
            print("Processing {} ads on page {}".format(len(new_ad_divs), page))
            processed_ad_divs.update(
                process_ad_divs(new_ad_divs, len(processed_ad_divs), driver, dirname, ad_limit, wait=wait))
            sleep(wait)
            all_ad_divs = driver.find_elements_by_css_selector(class_to_css_selector(ad_clazz))
            new_ad_divs = [ad_div for ad_div in all_ad_divs if ad_div not in processed_ad_divs]
            page += 1

        jar = requests.cookies.RequestsCookieJar()
        for cookie in driver.get_cookies():
            jar.set(cookie['name'], cookie['value'], domain=cookie['domain'], path=cookie['path'])

        ads_performance_logs = []
        ads_creative_logs = []
        for entry in driver.get_log('performance'):
            msg = json.loads(entry['message'])
            if msg.get('message', {}).get('method', {}) == 'Network.requestWillBeSent':
                url = msg['message']['params']['request']['url']
                if url.startswith('https://www.facebook.com/ads/archive/async/search_ads/'):
                    ads_creative_logs.append(msg)
                if url.startswith('https://www.facebook.com/ads/archive/async/insights/'):
                    ads_performance_logs.append(msg)

        # Ads creative
        print('Fetching creative XHRs')
        ads = []
        for count, msg in enumerate(ads_creative_logs):
            if count > 0:
                sleep(wait)
            r = requests.post(msg['message']['params']['request']['url'],
                              headers=msg['message']['params']['request']['headers'],
                              data=msg['message']['params']['request']['postData'],
                              cookies=jar)
            r.raise_for_status()
            payload = json.loads(r.text[9:])
            for ad_creative in payload['payload']['results']:
                if len(ads) < ad_limit:
                    ad = blank_ad()
                    ad['ad_archive_id'] = ad_creative['adArchiveID']
                    ad['page_name'] = ad_creative['pageName']
                    ad['page_id'] = ad_creative['pageID']
                    ad['html'] = ad_creative['snapshot']['body']['markup']['__html']
                    ad['byline'] = ad_creative['snapshot']['byline']
                    ad['caption'] = ad_creative['snapshot']['caption']
                    ad['title'] = ad_creative['snapshot']['title']
                    ad['link_description'] = ad_creative['snapshot']['link_description']
                    ad['display_format'] = ad_creative['snapshot']['display_format']
                    ad['instagram_actor_name'] = ad_creative['snapshot']['instagram_actor_name']
                    ad['page_like_count'] = ad_creative['snapshot']['page_like_count']
                    ad['creation_time'] = datetime.fromtimestamp(ad_creative['snapshot']['creation_time']).isoformat()
                    ad['start_date'] = datetime.fromtimestamp(ad_creative['startDate'])
                    if ad_creative['endDate']:
                        ad['end_date'] = datetime.fromtimestamp(ad_creative['endDate'])
                    ad['is_promoted_news'] = ad_creative['isPromotedNews']
                    ad['is_active'] = ad_creative['isActive']
                    ads.append(ad)

            with open('{}/ads-creative-{:04}.json'.format(dirname, count + 1), 'w') as file:
                json.dump(payload['payload'], file, indent=2)

            if ad_limit and ad_limit == len(ads):
                break

        # Ads performance
        print('Fetching performance XHRs')
        for count, msg in enumerate(ads_performance_logs):
            if count > 0:
                sleep(wait)
            r = requests.post(msg['message']['params']['request']['url'],
                              headers=msg['message']['params']['request']['headers'],
                              data=msg['message']['params']['request']['postData'],
                              cookies=jar)
            r.raise_for_status()
            payload = json.loads(r.text[9:])
            ad_performance = payload['payload']
            with open('{}/ads-performance-{:04}.json'.format(dirname, count + 1), 'w') as file:
                json.dump(ad_performance, file, indent=2)

            ad = ads[count]
            ad['impressions'] = ad_performance['impressions']
            ad['spend'] = ad_performance['spend']

        # Add screenshot and performance
        for count, ad in enumerate(ads):
            ad['screenshot'] = 'ad-{:04}.png'.format(count + 1)
            ad['performance'] = 'ads-performance-{:04}.json'.format(count + 1)

        with open('{}/ads.csv'.format(dirname), 'w') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=blank_ad().keys())
            writer.writeheader()
            writer.writerows(ads[:(ad_limit or len(ads))])

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
    parser.add_argument('--wait', help='Seconds to sleep between requests', default='1', type=int)
    country_choices = ('ALL', 'US', 'BR')
    parser.add_argument('--country',
                        help='Limit ads by country. Choices: {}. Default is {}.'.format(', '.join(country_choices),
                                                                                        'ALL'),
                        choices=country_choices,
                        default='ALL')
    type_choices = ('news_ads', 'political_and_issue_ads')
    parser.add_argument('--type',
                        help='Limit ads by type. Choices: {}. Default is {}.'.format(', '.join(type_choices),
                                                                                     'political_and_issue_ads'),
                        choices=type_choices,
                        default='political_and_issue_ads')
    status_choices = ('all', 'active', 'inactive')
    parser.add_argument('--status',
                        help='Limit ads by status. Choices: {}. Default is {}.'.format(', '.join(status_choices),
                                                                                       'all'),
                        choices=status_choices,
                        default='all')

    args = parser.parse_args()
    main(' '.join(args.query), args.country, args.type, args.status, args.email, args.password, ad_limit=args.limit,
         headless=not args.headed, wait=args.wait)
