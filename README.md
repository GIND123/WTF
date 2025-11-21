
# Yelp AI Pipelines Documentation

This repository contains **two pipelines** leveraging Yelp and Google Gemini APIs to interact with images, generate search queries, retrieve business information, and provide AI-powered reviews. Both pipelines integrate natural language processing and AI models to enhance the Yelp experience.  

---

## **Pipeline 1: Image-to-Yelp Query Pipeline**

### **Overview**
Pipeline 1 allows users to provide an image and a description prompt. The system generates a **natural-language Yelp search query** based on the image content and user preferences, queries Yelp’s AI API, and returns a list of relevant businesses.

### **Technologies Used**
- **Python 3**
- `requests` library for HTTP API calls
- `google-genai` Python client for Google Gemini API
- Yelp AI API (`YELP_AI_ENDPOINT`) for conversational query results
- Yelp Business API for structured business details

### **Functionality**
1. Accept an **image input** from the user.
2. Ask the user to **describe their preference** based on the image.
3. Use **Google Gemini** to generate a single, specific, natural-language Yelp query.
4. Query Yelp AI with the generated query to get business suggestions.
5. Parse the response and display:
   - Business name
   - Rating
   - Price level
   - Address
   - Yelp URL

[User Input: Image + Description]
           |
           v
[Read Image Bytes] 
           |
           v
[Google Gemini API: Generate Yelp Query]
           |
           v
[Truncate Query if needed]
           |
           v
[Yelp AI API: Execute Query]
           |
           v
[Parse Response]
           |
           v
[Output: Businesses with Name, Rating, Price, Address, URL]

## **Pipeline 2: Multi Agent Debate Pipeline**

Pipeline 2 is designed to automate the **critical analysis of Yelp businesses**. It leverages:

- **Yelp Business API** for structured metadata  
- **Yelp Reviews API** for real user reviews  
- **Yelp AI API** for AI-generated review summaries when review data is insufficient  
- **Google Gemini 2.5 models** to run a **three-agent internal debate**  

The output consists of **three lines**:
1. `Pros:` – positive aspects relevant to a first-time visitor  
2. `Cons:` – negative aspects and potential risks  
3. `Our verdict:` – a practical recommendation on when and for whom to visit  

---

## **Methodology**

### **Step 1: Input & Business ID Extraction**
- The user provides a Yelp business URL.  
- A helper function parses the URL to extract the **business ID**.  
- Example: `https://www.yelp.com/biz/luigis-pizzeria-san-francisco` → `luigis-pizzeria-san-francisco`.

---

### **Step 2: Fetch Business Metadata**
- Using the **Yelp Business API**, the pipeline retrieves:
  - Name
  - Rating
  - Price level
  - Categories
  - Address
- Structured metadata forms the foundation of the **context** used for AI evaluation.

---

### **Step 3: Fetch Review Data**
1. Query **Yelp Reviews API** to retrieve the top `n` reviews (default 6).  
2. Extract:
   - Ratings
   - Review text  
3. If the review set is too small or empty:
   - Use the **Yelp AI API** to generate a **summary of typical guest experiences**, including:
     - Three positive points  
     - Three negative points  

This ensures that the **three-agent system** always has sufficient evidence to form opinions.

---

### **Step 4: Build Context**
Two types of context are built for the AI:

1. **From Reviews**:
   - Concatenates business metadata with the most representative reviews.
   - Focuses on reviews relevant to:
     - Food quality  
     - Service  
     - Cleanliness  
     - Atmosphere

2. **From AI Summary**:
   - Combines business metadata with AI-generated bullet points.
   - Ensures context is complete even if user reviews are missing.

---

### **Step 5: Three-Agent Debate**
The core AI component uses **Google Gemini 2.5 models** with a fixed system prompt (`JUDGE_SYS`) to simulate an internal debate:

1. **Optimistic Agent**  
   - Focus: strengths, recurring positive patterns, why guests enjoy this place.  
   - Emphasizes high-quality food, service, value, convenience, and atmosphere.

2. **Critical Agent**  
   - Focus: weaknesses, recurring complaints, mismatches with expectations.  
   - Emphasizes inconsistent food quality, slow service, cleanliness issues, noise, or poor value.

3. **Judge Agent**  
   - Weighs both perspectives and outputs a **concise recommendation**.  
   - Output constraints:
     - Each line under 200 characters  
     - No explicit references to Yelp or review sources  
     - Practical guidance for first-time visitors  

**Internal Process**:
- Optimistic and Critical agents argue **silently**.
- Judge summarizes as:
Pros: <one sentence summarizing main positives>
Cons: <one sentence summarizing main negatives>
Our verdict: <practical recommendation>

yaml
Copy code

---

### **Step 6: Output**
- The final output is **three lines** printed to the console.  
- Example:
Pros, Cons, Our verdict:
Pros: Fresh ingredients, cozy ambiance, friendly staff.
Cons: Can be noisy during peak hours, limited seating.
Our verdict: Great for casual dinners, avoid weekends if you want quiet.



