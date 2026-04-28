FROM eclipse-temurin:21-jdk-alpine

# Install curl for healthcheck
RUN apk add --no-cache curl

WORKDIR /app

# Copy the JAR file
# Adjust the pattern if your JAR name is different
COPY target/Registery*.jar app.jar

# Create non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

EXPOSE 8888

# JVM optimized for containers
ENTRYPOINT ["java", \
    "-XX:+UseContainerSupport", \
    "-XX:MaxRAMPercentage=75.0", \
    "-jar", \
    "app.jar"]