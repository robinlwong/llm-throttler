import base64
import json
import os
import functions_framework
from google.cloud import billing_v1

# The project ID is typically passed as an environment variable in Cloud Functions
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
PROJECT_NAME = f"projects/{PROJECT_ID}"

@functions_framework.cloud_event
def stop_billing(cloud_event):
    """
    Triggered by a Pub/Sub message from a Cloud Billing Budget alert.
    """
    # 1. Decode the Pub/Sub payload
    pubsub_message = cloud_event.data["message"]
    pubsub_data = base64.b64decode(pubsub_message["data"]).decode("utf-8")
    alert_payload = json.loads(pubsub_data)

    cost_amount = alert_payload.get("costAmount")
    budget_amount = alert_payload.get("budgetAmount")
    
    # alertThresholdExceeded is provided as a decimal (e.g., 1.0 = 100%)
    threshold = alert_payload.get("alertThresholdExceeded", 0.0)

    print(f"Current cost: {cost_amount}, Budget: {budget_amount}. Threshold hit: {threshold * 100}%")

    # 2. Safety Check: Only execute if the 100% threshold is breached
    if threshold < 1.0:
        print("Budget not fully exhausted. No action taken.")
        return

    print("CRITICAL: Budget exceeded! Initiating billing kill-switch...")
    
    # 3. Instantiate the Billing Catalog Client
    client = billing_v1.CloudCatalogClient()

    # 4. Sever the billing connection
    # Setting billing_account_name to an empty string removes the project's billing association
    request = billing_v1.UpdateProjectBillingInfoRequest(
        name=PROJECT_NAME,
        project_billing_info=billing_v1.ProjectBillingInfo(
            billing_account_name="" 
        )
    )

    try:
        client.update_project_billing_info(request=request)
        print(f"SUCCESS: Billing disabled for project: {PROJECT_ID}. Downside risk capped.")
    except Exception as e:
        print(f"ERROR: Failed to disable billing. Immediate manual intervention required: {e}")
