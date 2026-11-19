# Gatuya Coffee Society System

Python + Streamlit + pandas + SQLite starter for a coffee society operations system.

## Run locally

1. Install Python 3.10 or newer.
2. In a terminal in this folder, run `python -m pip install -r requirements.txt` (repeat after changing `requirements.txt` to install the SMS library).
3. Run `streamlit run app.py`.

The application creates `gatuya_coffee.db` in this folder on first launch. Keep a backup of that file; it contains the pilot records.

## Set the authorized-personnel PIN

Farmer registration and manager corrections are locked until an admin PIN is configured.

1. In this project folder, create a folder named `.streamlit`.
2. Inside it, create `secrets.toml` with an admin PIN:

   ```toml
   admin_pin = "choose-your-own-pin"
   ```

3. To enable bulk SMS, add these values from your Africa's Talking app after getting an approved sender ID:

   ```toml
   sms_username = "your-app-username"
   sms_api_key = "your-private-api-key"
   sms_sender_id = "your-approved-sender-id"
   ```

   Keep API credentials private. The SMS page previews the audience and message and requires an explicit confirmation before submitting a campaign.
4. Restart Streamlit. Enter the PIN when opening Farmers, Store / stock, Meetings & messages, Manager corrections, or Feedback inbox.

Keep `.streamlit/secrets.toml` private. It is excluded from Git by `.gitignore`.

## Delivery rule

The database enforces one delivery per farmer share number per calendar date, across Cherry and Mbuni combined. This is enforced in SQL as well as checked by the application, so two simultaneous entries cannot bypass the rule. New delivery entries are limited to Tuesday through Friday. The operator enters a share number and confirms the displayed farmer name before weighing; the weighed time is saved to the second. The manager correction page requires a reason and keeps before/after values in an audit table. Farmer registration and corrections require the configured PIN.

Use **Management dashboard → Data & next steps → Add fictional demo farmers and two years of sample deliveries** to populate the app for a demonstration. These names and weights are simulated. Demo IDs, account numbers, and phone values use labels such as `DEMO-ID-0001`, `DEMO-ACCT-0001`, and `DEMO-PHONE-0001`; demo phones are deliberately non-routable. Test farmer access with share `DEMO-1001` and phone `DEMO-PHONE-0001`. The sample follows Tuesday–Friday delivery and models cherry from October through January and mbuni in February. Delivery history supports week, month, and year summaries. The overview shows one day's deliveries cumulatively and compares the selected week with the 100-tonne reference.

The Processing / washing page records washed time, cherry input and PP1, PP2, third-grade and light output. The Labour page records shifts and calculates KES 400 base shift pay for up to eight paid hours plus KES 50 per overtime hour. It subtracts the entered break (default 60 minutes); set the next calendar date for a shift ending after midnight.

Use **Data & next steps → Add example labour shifts** for fictional regular, overtime and overnight shift examples.

Farmer dashboard access matches the share number and registered phone number, and shows only that farmer's delivery history and totals. This is suitable for a local prototype; add one-time phone verification before publishing personal histories to the public internet. Meeting messages can be submitted through the configured Africa's Talking SDK. Share your thoughts is a public feedback form; after deploying the app, select that page and share the resulting browser URL. The app must be hosted on an internet-accessible service for farmers outside your local network to open it.

The app has separate Management dashboard and Farmer portal modes. The Farmer portal can be opened directly with `?portal=farmer` appended to the deployed app URL. The theme uses green, black, red and white, with a light background and readable dark text on main screens.

## Get a shareable web URL

Putting the project in GitHub stores its code; GitHub alone does not run the app. To get a URL, deploy the repository on [Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), choose `app.py` as the entry point, and add `admin_pin` in the app's Secrets settings. Community Cloud then assigns a `streamlit.app` URL. Do not upload `.streamlit/secrets.toml` or `gatuya_coffee.db`; `.gitignore` excludes both.

Use a demo deployment only until the app has individual staff accounts, a central PostgreSQL database, and verified farmer sign-in. The local SQLite database is not a shared, durable database for society operations.

After recording a delivery or issuing an agrochemical loan, use the **Download / print ... receipt (PDF)** button to save an A5 receipt and print it. The agrochemical page has **Add sample coffee agrochemical catalogue** for liquid, powder, wettable-powder, granule, and biological product examples. Sample catalogue entries do not add stock; record a supplier receipt before issuing a loan. Verify current registration and crop label with PCPB and the product supplier.

## Pilot notes

The app now has separate Management dashboard and Farmer portal experiences. The farmer portal includes individual kg history, agrochemical loan balances, upcoming meeting notices and feedback. The management side includes stock and loan records. Farmer access currently matches share number plus phone number; add verified one-time codes before publishing personal histories to the public internet.

This remains a local single-computer prototype. For several factory offices, host one central app and migrate the database to PostgreSQL; do not copy the SQLite database file between computers or run separate copies expecting them to share records. It still needs transit location tracking and public bidding / sale-income reporting. Existing records can be migrated once their file format and columns are known. Machine-learning forecasts need reliable historical seasons before their output is useful; the starter includes scikit-learn but does not show unsupported predictions.

Protect farmer IDs and account numbers with individual staff accounts, role-based access, backups and deployment security before putting real personal data into a networked installation. The current manager PIN is a prototype gate, not a substitute for individual accounts.
