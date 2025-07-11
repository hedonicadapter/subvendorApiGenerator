# Test comment to trigger pipeline (see if it works)

import logging
import azure.functions as func
import os
import json
import traceback
import base64
import hcl2

from dataclasses import dataclass
from parser import generate_openapi_schema, sanitize_schema_name

@dataclass
class RequestBody:
    contents: dict[str, str]

def decodeHcl(encoded_content):
    decoded_bytes = base64.b64decode(encoded_content)
    return decoded_bytes.decode('utf-8')

def getApiSpec(schemas, version):
    return {
        "openapi": "3.0.0", 
        "info": {
            "title": "Request Subscription API",
            "version": version
        },
        "paths": {
            "/requestSubscription": {
                "post": {
                    "summary": "Request a subscription",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": schemas
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Subscription requested successfully"
                        }
                    }
                }
            }
        }
    }

def main(req: func.HttpRequest, outputblob: func.Out[bytes]):
    try:
        data = req.get_json()
        req_body = RequestBody(**data)
        version = req.route_params.get('version')
    except ValueError as e:
        return func.HttpResponse(f"Invalid JSON: {str(e)}", status_code=400)
    except TypeError as e:
        return func.HttpResponse(f"Missing required field: {str(e)}", status_code=400)
    else:
        specs = {
            "type": "object",
            "properties": {
                "subscription_id":{ "type": "string", },
                "tenant_id":{ "type": "string", },
            },
            "additionalProperties": False,
            "required": ["subscription_id","tenant_id"] # TODO: add required tf variables dynamically
        }

        try:
            decoded_hcl = decodeHcl(req_body.contents) 
            hcldict = hcl2.loads(decoded_hcl)
            obj={}

            for item in hcldict["variable"]:
                for k, v in item.items():
                    obj[k] = v

            spec = generate_openapi_schema(obj)
            # schemaName = sanitize_schema_name(key)

            specs["properties"]["variables"] = spec
        except UnicodeDecodeError as e:
            logging.error(f"Base64 decoding failed: {str(e)}")
            return func.HttpResponse(f"Invalid base64 encoding.", status_code=400)
        except Exception as e:
            logging.error(f"Something failed: {str(e)}")
            logging.error(traceback.format_exc())
            return func.HttpResponse(f"Error processing: {str(e)}", status_code=400)            

        api_spec = getApiSpec(specs, version)
        outputblob.set(json.dumps(api_spec))
    
        return func.HttpResponse(
            f"Blob created successfully!",
            status_code=201
        )
