# Task 2 — n8n setup (khud karna hoga, ye no-code part hai)

Maine workflow design + backend API bana di hai. Ab tumhe bas n8n account
banake ye import karna hai. Neeche step by step:

## Step 1 — n8n account banao
1. https://n8n.io par jao, "Start for free" (Cloud trial) le lo. Ye sabse
   aasan hai, self-host ki zaroorat nahi.

## Step 2 — Apni machine pe backend API chalao
```
cd task2_n8n
pip install flask
python3 duplicate_check_api.py
```
Ye `people.db` (Task 1 wali) ke against check karta hai, port 5001 pe chalta hai.

## Step 3 — n8n Cloud ko apni local API tak pahunchao
n8n Cloud internet pe hai, tumhare laptop ke `localhost` tak nahi pahunch
sakta. Isliye ngrok use karo (free):
```
ngrok http 5001
```
Ye ek public URL dega jaisे `https://abcd1234.ngrok-free.app`. Ye URL
copy kar lo.

## Step 4 — Workflow import karo
1. n8n editor mein "Import from File" (ya "+" > Import) pe click karo.
2. `n8n_workflow.json` select karo.
3. "Check Against Database" node (HTTP Request) kholo aur URL field mein
   `http://localhost:5001/check` ki jagah apna ngrok URL + `/check` daal do.

## Step 5 — Email node set karo (ya Slack se replace karo)
"Send Duplicate Alert Email" node mein apni SMTP credentials daalni hongi
(Gmail app password use kar sakte ho — n8n docs mein SMTP credential setup
ka option hai). Agar email jhanjhat lage to isko Slack node se replace kar
sakte ho — logic same rahega, sirf output alag hoga. Agar dono setup na ho
paye to demo ke liye ek simple "HTTP Request" node laga do jo
webhook.site ke free test URL pe hit kare — video mein wahan alert aata
dikha sakte ho.

## Step 6 — Test karo
1. Workflow ko "Active" karo (ya test mode mein "Listen for test event").
2. Webhook node pe "Test URL" copy karo.
3. Ek sample CSV bhejo (isi repo mein `sample_new_applicants.csv` hai — isme
   ek naam already tumhare people.db mein hai, ek naya hai):
```
curl -X POST <webhook test URL> -F "data=@sample_new_applicants.csv"
```
4. Dekhna chahiye: purane naam (jo DB mein hai) ke liye alert fire ho,
   naye naam ke liye kuch na ho.

## Video mein kya dikhana hai
- Workflow ka canvas (saare nodes connected)
- Ek CSV bhejke live chalta hua dikhana (duplicate wala alert aata hue)
- Bolna: "isme koi hardcoded matching nahi hai, ye wahi email/phone matching
  rule use kar raha hai jo Task 1 ke merge_pipeline.py mein hai" — isse
  pata chalega ki tumne dono tasks ko properly connect kiya hai, alag-alag
  nahi banaye.
