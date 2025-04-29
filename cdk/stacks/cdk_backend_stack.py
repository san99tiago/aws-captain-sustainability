# Built-in imports
import os

# External imports
from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_iam,
    aws_lambda,
    aws_apigateway as aws_apigw,
    CfnOutput,
)
from constructs import Construct


class BackendStack(Stack):
    """
    Class to create the backend resources, for the Captain Planet API Backend on AWS.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        main_resources_name: str,
        app_config: dict[str],
        **kwargs,
    ) -> None:
        """
        :param scope (Construct): Parent of this stack, usually an 'App' or a 'Stage', but could be any construct.
        :param construct_id (str): The construct ID of this stack (same as aws-cdk Stack 'construct_id').
        :param main_resources_name (str): The main unique identified of this stack.
        :param app_config (dict[str]): Dictionary with relevant configuration values for the stack.
        """
        super().__init__(scope, construct_id, **kwargs)

        # Input parameters
        self.construct_id = construct_id
        self.main_resources_name = main_resources_name
        self.app_config = app_config
        self.deployment_environment = self.app_config["deployment_environment"]

        # Main methods for the deployment
        self.create_lambda_layers()
        self.create_lambda_functions()
        self.create_rest_api()
        self.configure_rest_api_simple()  # --> Simple example usage of REST-API (proxy)

        # Create CloudFormation outputs
        self.generate_cloudformation_outputs()

    def create_lambda_layers(self) -> None:
        """
        Create the Lambda layers that are necessary for the additional runtime
        dependencies of the Lambda Functions.
        """

        # Layer for "LambdaPowerTools" (for logging, traces, observability, etc)
        self.lambda_layer_powertools = aws_lambda.LayerVersion.from_layer_version_arn(
            self,
            "Layer-powertools",
            layer_version_arn=f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:71",
        )

        # Layer for "common" Python requirements (fastapi, pydantic, ...)
        self.lambda_layer_common = aws_lambda.LayerVersion(
            self,
            "Layer-common",
            code=aws_lambda.Code.from_asset("lambda-layers/common/modules"),
            compatible_runtimes=[
                aws_lambda.Runtime.PYTHON_3_11,
            ],
            description="Lambda Layer for Python with <common> library",
            removal_policy=RemovalPolicy.DESTROY,
            compatible_architectures=[aws_lambda.Architecture.X86_64],
        )

    def create_lambda_functions(self) -> None:
        """
        Create the Lambda Functions for the solution.
        """
        # Get relative path for folder that contains Lambda function source
        # ! Note--> we must obtain parent dirs to create path (that"s why there is "os.path.dirname()")
        PATH_TO_LAMBDA_FUNCTION_FOLDER = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "backend",
        )

        # Lambda Function for API Backend
        self.lambda_captain_planet: aws_lambda.Function = aws_lambda.Function(
            self,
            "Lambda-captain",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            function_name=f"{self.main_resources_name}-{self.deployment_environment}",
            handler="api/v1/main.handler",
            code=aws_lambda.Code.from_asset(PATH_TO_LAMBDA_FUNCTION_FOLDER),
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={
                "ENVIRONMENT": self.app_config["deployment_environment"],
                "LOG_LEVEL": self.app_config["log_level"],
            },
            layers=[
                self.lambda_layer_powertools,
                self.lambda_layer_common,
            ],
        )
        self.lambda_captain_planet.role.add_managed_policy(
            aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonBedrockFullAccess",
            ),
        )

    def create_rest_api(self):
        """
        Method to create the REST-API Gateway for exposing the "captain-planet"
        functionalities.
        """

        self.api = aws_apigw.LambdaRestApi(
            self,
            "RESTAPI",
            rest_api_name=self.app_config["api_gw_name"],
            description=f"REST API Gateway for {self.main_resources_name}",
            handler=self.lambda_captain_planet,
            deploy_options=aws_apigw.StageOptions(
                stage_name=self.deployment_environment,
                description=f"REST API for {self.main_resources_name} in {self.deployment_environment} environment",
                metrics_enabled=True,
            ),
            default_cors_preflight_options=aws_apigw.CorsOptions(
                allow_origins=aws_apigw.Cors.ALL_ORIGINS,
                allow_methods=aws_apigw.Cors.ALL_METHODS,
                allow_headers=["*"],
            ),
            endpoint_types=[aws_apigw.EndpointType.REGIONAL],
            cloud_watch_role=False,
            proxy=False,  # Proxy disabled to have more control
        )

    def configure_rest_api_simple(self):
        """
        Method to configure the REST-API Gateway with resources and methods (simple way).
        """

        # Define REST-API resources
        root_resource_api = self.api.root.add_resource("api")
        root_resource_v1 = root_resource_api.add_resource("v1")

        # Endpoints ("docs" without auth and "captain" with auth)
        root_resource_docs: aws_apigw.Resource = root_resource_v1.add_resource("docs")
        root_resource_captain = root_resource_v1.add_resource("captain")

        # Define all API-Lambda integrations for the API methods
        api_lambda_integration_captain = aws_apigw.LambdaIntegration(
            self.lambda_captain_planet
        )

        # Enable proxies for the "/api/v1/docs" endpoints
        root_resource_docs.add_method("GET", api_lambda_integration_captain)
        root_resource_docs.add_proxy(
            any_method=True,  # To don't explicitly add methods on the `proxy` resource
            default_integration=api_lambda_integration_captain,
        )

        # Enable proxies for the "/api/v1/captain" endpoints
        root_resource_captain.add_method("GET", api_lambda_integration_captain)
        root_resource_captain.add_method("POST", api_lambda_integration_captain)
        root_resource_captain.add_proxy(
            any_method=True,  # To don't explicitly add methods on the `proxy` resource
            default_integration=api_lambda_integration_captain,
        )

    def generate_cloudformation_outputs(self) -> None:
        """
        Method to add the relevant CloudFormation outputs.
        """

        CfnOutput(
            self,
            "DeploymentEnvironment",
            value=self.app_config["deployment_environment"],
            description="Deployment environment",
        )

        CfnOutput(
            self,
            "BACKEND_API_URL_CAPTAIN",
            value=f"https://{self.api.rest_api_id}.execute-api.{self.region}.amazonaws.com/{self.deployment_environment}/api/v1/captain",
            description="BACKEND_API_URL_CAPTAIN",
        )
