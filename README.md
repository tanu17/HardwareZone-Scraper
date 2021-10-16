## Instructions
1. source venv/bin/activate (create virtual environment https://gist.github.com/Geoyi/d9fab4f609e9f75941946be45000632b)
2. pip install wheel
3. cd hwZoneScraper
4. pip install -r requirements.txt  (scrapy startproject hwZone_scraper if creating a new project)
5. code .
6. Change Payload-data in spiders/hwZoneSpider.py
7. scrapy crawl <spider name> -O <output_file_name.csv>
