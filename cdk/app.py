#!/usr/bin/env python3

# Built-in imports
import os

# External imports
import aws_cdk as cdk

# Own imports
from helpers.add_tags import add_tags_to_app
from stacks.cdk_backend_stack import BackendStack


print("--> Deployment AWS configuration (safety first):")
print("CDK_DEFAULT_ACCOUNT", os.environ.get("CDK_DEFAULT_ACCOUNT"))
print("CDK_DEFAULT_REGION", os.environ.get("CDK_DEFAULT_REGION"))


app: cdk.App = cdk.App()


# Configurations for the deployment (obtained from env vars and CDK context)
DEPLOYMENT_ENVIRONMENT = os.environ.get("DEPLOYMENT_ENVIRONMENT", "prod")
MAIN_RESOURCES_NAME = app.node.try_get_context("main_resources_name")
APP_CONFIG = app.node.try_get_context("app_config")[DEPLOYMENT_ENVIRONMENT]

backend_stack: BackendStack = BackendStack(
    app,
    f"{MAIN_RESOURCES_NAME}-backend-{DEPLOYMENT_ENVIRONMENT}",
    MAIN_RESOURCES_NAME,
    APP_CONFIG,
    env={
        "account": os.environ.get("CDK_DEFAULT_ACCOUNT"),
        "region": os.environ.get("CDK_DEFAULT_REGION"),
    },
    description=f"Stack for {MAIN_RESOURCES_NAME} backend infrastructure in {DEPLOYMENT_ENVIRONMENT} environment",
)

add_tags_to_app(
    app,
    MAIN_RESOURCES_NAME,
    DEPLOYMENT_ENVIRONMENT,
)

app.synth()
