#!/bin/bash
cd C:/MenoAPI/API

nohup C:/ProgramData/anaconda3/python C:/MenoAPI/API/src/webhook_starter.py > C:/MenoAPI/API/logs/output_run.log 2>&1 &