FROM nginx:alpine

COPY gloss-recommender/public /usr/share/nginx/html
COPY gloss-recommender/nginx.conf /etc/nginx/templates/default.conf.template

# API 호스트는 compose의 API_HOST로 치환한다. $host 등 nginx 변수는 건드리지 않는다.
ENV NGINX_ENVSUBST_FILTER=API_HOST
ENV API_HOST=api-1107

# 데이터는 api 컨테이너만 읽는다. UI는 /api/ 로만 접근하므로
# nginx 이미지에 사본을 두지 않는다. nginx.conf 의 /data/ 경로는 비어 있다.

EXPOSE 80
