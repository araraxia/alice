# alice

Alice is a personal Flask/WSGI API and web server meant to handle various automations and showcase neat things sometimes. The site can be viewed live at https://araxia.xyz/.

### Primary features include:
- Hosting web pages with varying scripts and styling as a digital playground to learn and experiment with new things.
  - Current index page is a rendetion of [Demonin's Item Shop's Index Page](https://demonin.com/) <[Github](https://github.com/DemoninCG)>, with plans on building off their current logic into my own shader formula. 
- Updating a personal postgreSQL server with live Old-School RuneScape item price data from the [OSRS Wiki Prices API](https://oldschool.runescape.wiki/w/RuneScape:Real-time_Prices).
- Running and presenting various item price calculations such as:
  - Optimal buy/sell prices to create Super Combat Potions.
  - Optimal buy/sell prices for Goading and Prayer regen potions, including production costs and profit/hr.
  - Item price fluctionation notifications for all items over a given value per daily volume. [Planned]
  - Item look up with price/time and trade volume/time analysis and graphing [WIP]. I'm looking to expand this by linking items to other related items to precache the related item data. [Planned]
- Dynamically hosting personal documentation to be accessed by user accounts. [WIP]

> Individual scripts can be found in `src/scripts`.
