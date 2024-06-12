FROM python:3.10.7-slim-buster

ENV TZ="Asia/Amman"

COPY . .

RUN apt-get update

RUN apt-get --assume-yes install nano

RUN apt-get --assume-yes install git

RUN pip install --upgrade pip

RUN pip install -r requirements.txt

EXPOSE 3000

# Run app.py when the container launches
# CMD ["python", "app.py"]
CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0", "--port=3000"]