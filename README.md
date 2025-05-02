# TLS Report Aggregator

Just another one of those since I didn't find one doing what I wanted. It consists of three services:

### tlsreport.py

A python script that fetches Mails from an IMAP server, parses them if they are TLS Reports and stores the report 
data in the 

### MariaDB 

Central database for the system to permanently store data about received reports. 
I am far from being a database expert but I think I built a scheme that works for this ;)

And then there's 

### Grafana 

to turn the stored data into something human readable. It comes with a preconfigured simple dashboard but again,
I am sure there's others out there who can do more with it. 

If you build a cool dashboard to show the collected data in better ways let me know!

## Installation

Easiest way would be to clone this repository to your docker host and copy `example.env` to `.env`

All variables in the .env file should be self-explanatory.

Then run `docker compose up -d` to start everything...  

It will pull and build the needed images and run everythong. By default you then find the dashboard on port 3000