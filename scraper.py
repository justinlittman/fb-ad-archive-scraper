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


def find_next_link(driver):
    try:
        return driver.find_element_by_link_text('See More')
    except NoSuchElementException:
        return None


def blank_ad():
    return {'ad_count': None,
            'page': None,
            'is_active': None,
            'start': None,
            'end': None,
            'paid_for_by': None,
            'title': None,
            'text': None}


def process_ad_divs(ad_divs, ad_count, page_count, driver, writer, dirname, ad_limit):
    # Add whitespace to bottom to allow scrolling to bottom row
    window_height = driver.execute_script('return window.innerHeight')
    driver.execute_script("arguments[0].setAttribute('style', 'margin-bottom:{}px;')".format(window_height),
                          ad_divs[-1])
    for ad_div in ad_divs:
        ad_count += 1
        print('Ad {}'.format(ad_count))
        screenshot(ad_div, ad_count, dirname, driver)
        ad = blank_ad()
        ad['ad_count'] = ad_count
        ad['page'] = page_count
        ad['title'] = ad_div.find_element_by_xpath('.//a[text()]').text
        for span in ad_div.find_elements_by_xpath('.//span[text()]'):
            if span.text.startswith('Paid for by '):
                ad['paid_for_by'] = span.text[12:]
        for pos, div in enumerate(ad_div.find_elements_by_xpath('.//div[text()]')):
            if pos == 0:
                ad['is_active'] = div.text == 'Active'
            elif pos == 1:
                if div.text.startswith('Started running on '):
                    ad['start'] = div.text[19:]
                else:
                    split_text = div.text.split(' - ')
                    ad['start'] = split_text[0]
                    ad['end'] = split_text[1]
            elif not ('See Ad Performance' in div.text or (pos == 2 and div.text.startswith('Sponsored'))):
                if ad['text'] is None:
                    ad['text'] = div.text.replace('\n', ' ')
                else:
                    ad['text'] = ' '.join((ad['text'], div.text.replace('\n', ' ')))
        writer.writerow(ad)
        if ad_limit == ad_count:
            break

    return ad_count


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



def fullpage_screenshot(driver, filename):
    scrollheight = driver.execute_script('return Math.max( document.body.scrollHeight, '
                                         'document.body.offsetHeight, '
                                         'document.documentElement.clientHeight, '
                                         'document.documentElement.scrollHeight, '
                                         'document.documentElement.offsetHeight);')
    windowheight = driver.execute_script('return window.innerHeight')
    slices = []
    offset = 0
    imgheight = 0
    last_offset = 0
    while offset < scrollheight:
        driver.execute_script("window.scrollTo(0, %s);" % offset)
        img = Image.open(BytesIO(driver.get_screenshot_as_png()))
        imgheight += img.size[1]
        last_offset = offset
        offset += windowheight
        slices.append(img)

    screenshot_img = Image.new('RGB', (slices[0].size[0], imgheight))
    offset = 0
    # Crop the last image.
    width = slices[0].size[0]
    height = slices[0].size[1]
    last_height = (scrollheight - last_offset) * 2
    slices[-1] = slices[-1].crop((0, height - last_height, width, height))

    for img in slices:
        screenshot_img.paste(img, (0, offset))
        offset += img.size[1]

    screenshot_img.save(filename)


def main(q, fb_email, fb_password, ad_limit=None):
    timestamp = datetime.now()
    # Create directory
    dirname = '{}-{}'.format(q.replace(' ', '_'), timestamp.strftime('%Y%m%d%H%M%S'))
    os.makedirs(dirname)
    write_readme(dirname, timestamp, q, ad_limit)

    options = webdriver.ChromeOptions()
    options.add_argument("headless")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    try:
        driver.get(
            'https://www.facebook.com/politicalcontentads/?{}'.format(urlencode({'active_status': 'all', 'q': q})))
        driver.find_element_by_name('email').send_keys(fb_email)
        driver.find_element_by_name('pass').send_keys(fb_password)
        driver.find_element_by_name('login').click()
        sleep(5)

        try:
            driver.find_element_by_xpath('//span[text()="Log into Facebook"]')
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
        topnav_div = find_topnav_div(driver)
        assert topnav_div
        driver.execute_script("arguments[0].setAttribute('style', 'position: absolute; top: 0px;')", topnav_div)

        # Find the ad class
        print('Finding ad class')
        ad_clazz = find_ad_class(driver)
        assert ad_clazz

        with open('{}/ads.csv'.format(dirname), 'w') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=blank_ad().keys())
            writer.writeheader()

            page = 1
            ad_count = 0
            ad_divs = driver.find_elements_by_css_selector(class_to_css_selector(ad_clazz))
            print("Processing {} ads on page {}".format(len(ad_divs), page))
            ad_count = process_ad_divs(ad_divs, ad_count, page, driver, writer, dirname, ad_limit)
            next_link = find_next_link(driver)
            while next_link and ad_limit != ad_count:
                driver.execute_script("return arguments[0].scrollIntoView(true);", next_link)
                next_link.click()
                page += 1
                sleep(5)
                ad_divs = driver.find_elements_by_css_selector(class_to_css_selector(ad_clazz))
                print("Processing {} ads on page {}".format(len(ad_divs) - ad_count, page))
                ad_count = process_ad_divs(ad_divs[ad_count:], ad_count, page, driver, writer, dirname, ad_limit)
                next_link = find_next_link(driver)

    finally:
        driver.close()
        driver.quit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scrape Facebook\'s Archive of Ads with Political Content')
    parser.add_argument('email', help='Email address for FB account')
    parser.add_argument('password', help='Password for FB account')
    parser.add_argument('query', help='Query', nargs='+')
    parser.add_argument('--limit', help='Limit on number of ads to scrape', type=int)

    args = parser.parse_args()
    main(' '.join(args.query), args.email, args.password, ad_limit=args.limit)
