Cat Companion: A gamified daily quest tracker. Use the web dashboard to set your goals and interact with a 3D-printed cat to level up your bond! Built with CircuitPython, ESP32-S2/S3, and a touch of feline magic.

# How to run everything
## Web dashboard
1. Connect to phone hotspot/Wi-Fi  
- Frontend (requires node.js version v18.17.0 or newer)
  1. npm install
  2. nvm use 18.17.0
  3. npm run dev
- Backend
  1. pip install fastapi uvicorn
  2. uvicorn main:app --host 0.0.0.0 --port 8000
## Feather 
1. Connect to the same phone hotspot/Wi-Fi as the computer 
   - If you are using a phone hotspot, make sure to turn on “Maximize Compatibility” in settings so the Feather can connect to it 
2. Set up backend url for data fetching (see comments in the code.py file for more explanation)
3. Run code.py on MU Editor

