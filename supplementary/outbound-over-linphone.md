# Outbound calls over Linphone

If your Twilio free trial is exhausted, you can try to use [Linphone](https://www.linphone.org/en/) to make outbound calls.

## Steps

Follow these steps to make outbound calls over linphone:

### 1. Set up a Linphone account

- Go to [linphone.org](https://subscribe.linphone.org/register/email) and create a new account.

- After the account is created, you will receive your SIP address, which is usually `sip:<your-username>@sip.linphone.org`. Make a note of this.

### 2. Update livekit starter

- (If you're not using the livekit starter, skip this step)
- Go to https://github.com/murf-ai/murf-livekit-starter and get the latest code
- If there are conflicts, you can just manually add the files in https://github.com/murf-ai/murf-livekit-starter/tree/main/backend/src/telephony/outbound to your project.

### 3. Set up Livekit cloud

- If you haven't already, create a new Livekit account at [livekit.com](https://cloud.livekit.io/login).

- Create a new project and fetch your Livekit URL, API key, and API secret; Save these as `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` in your `.env` (or `.env.local`) file in the `/backend` folder.

### 4. Create a trunk

- In Livekit cloud, under the Telephony section, click on "SIP Trunks"
- Create a new outbound trunk with the following details:

```json
{
  "name": "linphone-trunk",
  "address": "sip.linphone.org",
  "transport": "SIP_TRANSPORT_TLS",
  "numbers": ["sip:<your-linphone-username>"]
}
```

- After the trunk is created, you will receive a TRUNK ID. Save this as `LIVEKIT_SIP_OUTBOUND_TRUNK_ID` in your .env file in the `/backend` folder.

### 5. Set up Linphone app

- Download and install the Linphone app for your phone. Log in with the linphone.org credentials.

- After you've logged in, you will need to give the app permission to access the microphone.

- Then in the linphone app, go to Settings -> Calls -> Advanced calls settings -> Turn "Media encryption mandatory" OFF.

### 6. Start the agent

- In the livekit starter, go to the `/backend` folder
- First run the agent using - `uv run python src/telephony/outbound/agent.py dev`
- Then make a call to your Linphone account - `uv run python src/telephony/outbound/dial.py --to <your-linphone-username>`
- You will receive a call on your Linphone app, and you can start talking to the agent.

- If you're not using the livekit starter, you can still refer to the code in https://github.com/murf-ai/murf-livekit-starter/tree/main/backend/src/telephony/outbound to implement your own solution.
