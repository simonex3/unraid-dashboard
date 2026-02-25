FROM nginx:alpine
RUN apk add --no-cache python3
COPY index.html /usr/share/nginx/html/index.html
COPY nginx.conf /etc/nginx/nginx.conf
COPY speedtest_server.py /speedtest_server.py
COPY start.sh /start.sh
RUN chmod -R 755 /usr/share/nginx/html && chown -R nginx:nginx /usr/share/nginx/html \
    && chmod +x /start.sh
EXPOSE 8888
CMD ["/start.sh"]
