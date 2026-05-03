# communib

## Technology Stack
### Frontend
* Vue
* Vite
* Javascript

### Backend
* Python
* Django

## Local Testing
You can use docker-compose to build a set of local containers to test locally prior to pusing your changes to the production branch. This process will build trhe following containers:

1. db - postgres database 
2. communib-backend - The backend django server written in python.
3. communib-frontend - The frontend vite/vue/javascript server.

To run the containers, from the django root directory:

```
# To build and start the 3 containers.
docker compose build
docker compose up

# To run the containers as daemons.
docker compose up -d

# To stop the containers.
docker compose stop
```
Not that using docker compose down will wipe away any data in the db, so I avoid it.

## Remote deploy
Build the frontend and push it to gcr.io.
```
cd frontend
docker buildx build --no-cache --platform linux/amd64,linux/arm64 --output "type=image,push=true" -t gcr.io/communib/communib-frontend:latest .
```

Build the backend and push it to gcr.io.
```
cd backend
docker buildx build --platform linux/amd64,linux/arm64 --output "type=image,push=true" -t gcr.io/communib/communib-backend:latest .
```

Go to the google console then go to Cloud Run. From Overview, select the resource to build (either communib or django-backend). Select "Edit & deploy new revision". Pick the new "Container Image URL" and hit "Deploy".