# fb-ad-archive-scraper
Scraper for Facebook's [Archive of Ads with Political Content](https://www.facebook.com/politicalcontentads) _... until Facebook provides an API._

fb-ad-archive-scraper will produce:
* CSV containing the text and metadata of the ads.
* Screenshots of each ad.
* A README file.

Like any scraper, fb-ad-archive-scraper is fragile. It will break if Facebook changes the structure / code of the 
Archive. If fb-ad-archive-scraper breaks, let me know.

Tickets / PRs are welcome.

## Install
1. Clone the repo:

        git clone https://github.com/justinlittman/fb-ad-archive-scraper.git

2. Change to the directory:

        cd fb-ad-archive-scraper

3. Optionally, create a virtual environment:

        virtualenv -p python3 ENV
        source ENV/bin/activate
        
4. Install requirements:

        pip install -r requirements.txt
        
5. [Install Chromedriver](https://sites.google.com/a/chromium.org/chromedriver/). On a Mac, this is:

        brew cask install chromedriver
        
   If already installed, upgrade Chromedriver with:

        brew cask upgrade chromedriver
        
## Usage

        usage: scraper.py [-h] [--limit LIMIT] [--headed] [--wait WAIT]
                          [--country {ALL,US,BR}]
                          [--type {news_ads,political_and_issue_ads}]
                          [--status {all,active,inactive}]
                          email password query [query ...]
        
        Scrape Facebook's Archive of Ads with Political Content
        
        positional arguments:
          email                 Email address for FB account
          password              Password for FB account
          query                 Query
        
        optional arguments:
          -h, --help            show this help message and exit
          --limit LIMIT         Limit on number of ads to scrape
          --headed              Use a headed chrome browser
          --wait WAIT           Seconds to sleep between requests
          --country {ALL,US,BR}
                                Limit ads by country. Choices: ALL, US, BR. Default is
                                ALL.
          --type {news_ads,political_and_issue_ads}
                                Limit ads by type. Choices: news_ads,
                                political_and_issue_ads. Default is
                                political_and_issue_ads.
          --status {all,active,inactive}
                                Limit ads by status. Choices: all, active, inactive.
                                Default is all.
                          
For example:

        python scraper.py fbuser@gmail.com password pelosi
        
Notes:
* fb-ad-archive-scraper uses a headless Chrome browser. This means that you will not see the browser at work.
* The output of each run will be placed in a separate directory and include a README, CSV file summarizing the ads, PNG images, and JSON retrieved from Facebook.

_The approach of extracting data from XHRs came from Ranjit Hatnagar._