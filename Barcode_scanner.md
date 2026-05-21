# Barcode Scanning Guide for EAN Reader

This guide explains how to scan barcodes and send them to the EAN Reader integration.

## Method 1: Mobile App Sharing (Default)

This is the **recommended method** for most users. No webhook configuration needed!

### How It Works

1. Scan barcode with any scanner app
2. Share/send the barcode to Home Assistant
3. Integration automatically processes it
4. Product added to shopping list (if enabled)

### Compatible Apps

#### iOS

**1. QR Reader for iPhone (Free)**
- Download from App Store
- Scan barcode
- Tap "Share" button
- Select "Home Assistant"
- Done!

**2. Barcode Scanner - QR Code (Free)**
- Scan barcode
- Tap the share icon
- Choose "Home Assistant"
- Barcode automatically sent

**3. Home Assistant Companion App Built-in Scanner**
- Open Home Assistant app
- Hamburger menu → Tools → Barcode Scanner (if available)
- Or use Shortcuts app to automate

#### Android

**1. Barcode Scanner by ZXing Team (Free)**
- Most popular Android scanner
- Scan barcode
- Tap "Share via SMS/Email"
- Select "Home Assistant"
- Barcode sent automatically

**2. QR & Barcode Scanner by Gamma Play (Free)**
- Scan barcode
- Tap share icon
- Choose "Home Assistant"
- Done!

**3. Home Assistant Companion App**
- Some versions have built-in scanner
- Check app settings

### Step-by-Step: iOS Example

Using "QR Reader for iPhone":

1. **Install QR Reader**
   - App Store → Search "QR Reader"
   - Install (free)

2. **First Scan**
   - Open QR Reader app
   - Point camera at barcode
   - App automatically detects and displays barcode

3. **Share to Home Assistant**
   - Tap "Share" button (usually top right)
   - Scroll and select "Home Assistant"
   - First time: May ask to allow sharing

4. **What Happens**
   - Home Assistant receives barcode
   - EAN Reader looks it up in OpenFoodFacts
   - Product name retrieved
   - Added to shopping list (if auto-add enabled)
   - Notification shown (if enabled)

### Step-by-Step: Android Example

Using "Barcode Scanner by ZXing":

1. **Install Scanner**
   - Google Play → Search "Barcode Scanner"
   - Install "Barcode Scanner" by ZXing Team

2. **Scan Barcode**
   - Open app
   - Point at barcode
   - Waits for you to center it
   - Beep when detected

3. **Share Result**
   - Tap "Share via SMS/Email" button
   - Select "Home Assistant" from list
   - May need to enable Home Assistant first time

4. **Automatic Processing**
   - Barcode sent to Home Assistant
   - Product looked up
   - Added to shopping list

### Tips for Mobile App Method

**Scanning Tips:**
- Good lighting helps
- Hold camera steady
- Get close enough (but not too close)
- Make sure entire barcode is visible
- Clean camera lens if having issues

**Troubleshooting:**
- If Home Assistant not in share menu:
  - Open Home Assistant app first
  - Try sharing any text to "wake up" the share option
  - Restart Home Assistant app
  - Reinstall Home Assistant app if needed

**Automation:**
- Some apps support iOS Shortcuts or Android Tasker
- Can automate: Scan → Auto-share → Done
- Advanced: NFC tag → Open scanner → Auto-share

### What Happens Behind the Scenes

When you share a barcode:

1. Scanner app extracts barcode number (e.g., "7318690101234")
2. Sends it to Home Assistant via `mobile_app.share` event
3. EAN Reader integration listens for these events
4. Validates barcode format (8-14 digits)
5. Looks up in local database first
6. If not found, queries OpenFoodFacts API
7. Saves product name
8. Adds to shopping list (optional)
9. Shows notification (optional)

All happens in 1-2 seconds!

---

## Method 2: Webhook (For External Scanners)

Use this method for **hardware barcode scanners**, **dedicated scanning devices**, or **custom integrations**.

### When To Use Webhook

✅ **Good for:**
- USB/Bluetooth barcode scanners
- Dedicated scanning hardware
- Point-of-sale (POS) devices
- Custom web interfaces
- External systems integrating with Home Assistant
- IoT barcode scanning projects

❌ **Not needed for:**
- Mobile phone scanning (use Method 1)
- One-off manual scans (use services)

### Enable Webhook

1. Go to Settings → Devices & Services
2. Find "EAN Reader" integration
3. Click "Configure"
4. Enable "Enable webhook" toggle
5. Click "Submit"
6. Restart Home Assistant (may be required)

### Get Webhook URL

After enabling:

1. Check Home Assistant logs for:
   ```
   Webhook registered with ID: abc123def456
   ```

2. Your webhook URL is:
   ```
   http://your-home-assistant:8123/api/webhook/abc123def456
   ```

3. Or with external URL:
   ```
   https://your-home-assistant-url/api/webhook/abc123def456
   ```

### Send Barcode via Webhook

**HTTP POST Request:**

```bash
curl -X POST \
  http://your-home-assistant:8123/api/webhook/YOUR_WEBHOOK_ID \
  -H "Content-Type: application/json" \
  -d '{"ean": "7318690101234"}'
```

**Request Format:**

```json
POST /api/webhook/YOUR_WEBHOOK_ID
Content-Type: application/json

{
  "ean": "7318690101234"
}
```

**Alternative field names** (all work):
- `ean`
- `barcode`
- `code`

**Response:**

```json
{
  "status": "success",
  "ean": "7318690101234",
  "name": "Oatly Oat Milk 1L",
  "source": "openfoodfacts",
  "added_to_list": true
}
```

### Hardware Scanner Examples

#### 1. USB Barcode Scanner (Keyboard Wedge)

Most USB scanners act as keyboards. Configure them to:

1. Scan barcode
2. Send barcode digits
3. Press Enter
4. Send webhook HTTP POST

**Using Python script:**

```python
#!/usr/bin/env python3
import requests
import sys

WEBHOOK_URL = "http://homeassistant.local:8123/api/webhook/YOUR_WEBHOOK_ID"

def send_barcode(barcode):
    """Send barcode to Home Assistant."""
    try:
        response = requests.post(
            WEBHOOK_URL,
            json={"ean": barcode},
            timeout=10
        )
        result = response.json()
        print(f"✓ {result.get('name', 'Unknown')}")
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    # Read barcode from stdin or argument
    barcode = sys.argv[1] if len(sys.argv) > 1 else input("Scan: ")
    send_barcode(barcode.strip())
```

**Usage:**
```bash
# Manual
python3 scanner.py 7318690101234

# From USB scanner (keyboard input)
python3 scanner.py  # Then scan barcode
```

#### 2. Bluetooth Scanner

**Using Node-RED:**

```json
[
    {
        "id": "scan_input",
        "type": "bluetooth in",
        "name": "Barcode Scanner",
        "characteristic": "scan",
        "wires": [["send_webhook"]]
    },
    {
        "id": "send_webhook",
        "type": "http request",
        "name": "Send to HA",
        "method": "POST",
        "url": "http://homeassistant:8123/api/webhook/YOUR_ID",
        "wires": [["debug"]]
    }
]
```

#### 3. ESP32/Arduino Scanner

```cpp
#include <WiFi.h>
#include <HTTPClient.h>

const char* webhook = "http://192.168.1.100:8123/api/webhook/YOUR_ID";

void sendBarcode(String barcode) {
    HTTPClient http;
    http.begin(webhook);
    http.addHeader("Content-Type", "application/json");
    
    String payload = "{\"ean\":\"" + barcode + "\"}";
    int httpCode = http.POST(payload);
    
    if (httpCode == 200) {
        Serial.println("✓ Sent: " + barcode);
    } else {
        Serial.println("✗ Error: " + String(httpCode));
    }
    
    http.end();
}
```

#### 4. Raspberry Pi Scanner

**Using Python + physical scanner:**

```python
#!/usr/bin/env python3
import evdev
import requests

WEBHOOK = "http://homeassistant:8123/api/webhook/YOUR_ID"

# Find scanner device
devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
scanner = None
for device in devices:
    if "barcode" in device.name.lower():
        scanner = device
        break

if not scanner:
    print("No scanner found!")
    exit(1)

print(f"Using: {scanner.name}")

# Listen for scans
barcode = ""
for event in scanner.read_loop():
    if event.type == evdev.ecodes.EV_KEY:
        key = evdev.categorize(event)
        if key.keystate == 1:  # Key down
            if key.keycode == 'KEY_ENTER':
                # Send complete barcode
                requests.post(WEBHOOK, json={"ean": barcode})
                print(f"Sent: {barcode}")
                barcode = ""
            else:
                # Build barcode
                barcode += key.keycode[-1]
```

### Web Interface Example

**Simple HTML form:**

```html
<!DOCTYPE html>
<html>
<head>
    <title>EAN Scanner</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 400px;
            margin: 50px auto;
            padding: 20px;
        }
        input {
            width: 100%;
            padding: 10px;
            font-size: 18px;
            margin: 10px 0;
        }
        button {
            width: 100%;
            padding: 15px;
            font-size: 18px;
            background: #03a9f4;
            color: white;
            border: none;
            border-radius: 5px;
        }
        #status {
            margin-top: 20px;
            padding: 10px;
            border-radius: 5px;
        }
        .success { background: #4caf50; color: white; }
        .error { background: #f44336; color: white; }
    </style>
</head>
<body>
    <h1>EAN Scanner</h1>
    <input type="text" id="barcode" placeholder="Scan or type barcode" autofocus>
    <button onclick="sendBarcode()">Send to Home Assistant</button>
    <div id="status"></div>

    <script>
        const WEBHOOK = 'http://homeassistant:8123/api/webhook/YOUR_ID';
        
        document.getElementById('barcode').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendBarcode();
            }
        });
        
        async function sendBarcode() {
            const barcode = document.getElementById('barcode').value;
            const status = document.getElementById('status');
            
            if (!barcode) {
                status.textContent = 'Please enter a barcode';
                status.className = 'error';
                return;
            }
            
            try {
                const response = await fetch(WEBHOOK, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ean: barcode})
                });
                
                const result = await response.json();
                
                if (result.status === 'success') {
                    status.textContent = `✓ ${result.name || 'Product scanned'}`;
                    status.className = 'success';
                    document.getElementById('barcode').value = '';
                } else {
                    status.textContent = `✗ ${result.message || 'Error'}`;
                    status.className = 'error';
                }
            } catch (error) {
                status.textContent = `✗ ${error.message}`;
                status.className = 'error';
            }
        }
    </script>
</body>
</html>
```

### Security Considerations

**Webhook is unauth by design** - anyone with URL can send barcodes.

**Recommended protections:**

1. **Local network only** - Don't expose webhook externally
2. **Firewall rules** - Block external access to webhook port
3. **VPN** - Use VPN for remote access
4. **Rate limiting** - Integration has built-in rate limiting
5. **Monitoring** - Check `binary_sensor.ean_reader_api_problem`

**If you need external access:**
- Use Home Assistant's external URL with SSL
- Use Nabu Casa cloud URL
- Set up reverse proxy with authentication
- Monitor access logs

### Troubleshooting Webhook

**Webhook not working:**

1. **Check webhook is enabled**
   - Integration options → Enable webhook = ON

2. **Find webhook ID**
   - Check Home Assistant logs
   - Look for: "Webhook registered with ID: ..."

3. **Test with curl**
   ```bash
   curl -X POST \
     http://homeassistant.local:8123/api/webhook/YOUR_ID \
     -H "Content-Type: application/json" \
     -d '{"ean":"7318690101234"}' \
     -v
   ```

4. **Check response**
   - Should return JSON with status
   - If 404: Wrong webhook ID
   - If timeout: Network issue
   - If 500: Integration error (check logs)

5. **Enable debug logging**
   ```yaml
   # configuration.yaml
   logger:
     default: info
     logs:
       custom_components.ean_reader: debug
   ```

**Common issues:**

- Wrong webhook ID → Check logs
- Wrong URL format → Use full `http://` URL
- Network blocked → Check firewall
- JSON format wrong → Use `Content-Type: application/json`
- Home Assistant not reachable → Check connectivity

---

## Comparison: Mobile vs Webhook

| Feature | Mobile App Sharing | Webhook |
|---------|-------------------|---------|
| Setup | Zero config | Enable + find webhook ID |
| Best For | Household shopping | Automated systems |
| Hardware | Phone camera | USB/BT scanners |
| Cost | Free | May need hardware |
| Reliability | Very high | Depends on network |
| Offline | No (needs HA connection) | No (needs HA) |
| Speed | 1-2 seconds | <1 second |
| Range | Anywhere with internet | Local network |

**Recommendation:**
- 👥 **Personal/household use** → Mobile app sharing
- 🏭 **Business/automation** → Webhook + hardware scanner
- 🏪 **Point of sale** → Webhook + USB scanner
- 🚚 **Inventory management** → Webhook + handheld scanner

---

## Advanced: Multiple Scanner Stations

You can set up multiple scanning stations using webhooks:

**Kitchen Station** (Raspberry Pi + USB scanner):
```python
# kitchen_scanner.py
WEBHOOK = "http://homeassistant:8123/api/webhook/abc123"
# Auto-scan and send
```

**Garage Station** (ESP32 + barcode module):
```cpp
const char* webhook = "http://homeassistant/api/webhook/abc123";
// Physical button + scanner
```

**Mobile Station** (Phone):
- Use mobile app sharing method
- No webhook needed

All feed into same shopping list!

---

## Testing

**Test with known barcode:**

1. **Nutella** (International): `3017624010701`
2. **Coca-Cola** (International): `5449000000996`
3. **Oatly Oat Milk** (Sweden): `7318690101234`

**Test webhook:**
```bash
curl -X POST \
  http://homeassistant.local:8123/api/webhook/YOUR_ID \
  -H "Content-Type: application/json" \
  -d '{"ean":"3017624010701"}'
```

**Expected response:**
```json
{
  "status": "success",
  "ean": "3017624010701",
  "name": "Nutella ...",
  "source": "openfoodfacts",
  "added_to_list": true
}
```

---

## Need Help?

- **Mobile app not working** → Check sharing permissions
- **Webhook issues** → Check logs, test with curl
- **Product not found** → Try a different barcode to test
- **Rate limited** → Check `binary_sensor.ean_reader_api_problem`

**Still stuck?** Open an issue: https://github.com/swetoast/ha-ean-reader/issues
