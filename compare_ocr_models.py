#!/usr/bin/env python3
"""
Performance & Cost Comparison: Gemini 2.5 Flash vs Gemini 2.5 Flash-Lite
Evaluates OCR accuracy, speed, and cost for astrology text extraction.
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
import pandas as pd
from tabulate import tabulate
from pdf2image import convert_from_path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.rag.extraction.vision_extractor import VisionExtractor, ExtractionConfig
from src.utils.cost_logger import get_cost_logger

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=project_root / ".env")
except ImportError:
    pass

def run_comparison(pdf_path, pages_to_test):
    # 0. SETUP AUTH: Ensure credentials file is set for Vertex AI
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        default_creds = project_root / "google_credentials.json"
        if default_creds.exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(default_creds)
            print(f"🔑 Using Credentials: {default_creds}")

    # Create output directory for comparison
    output_dir = Path("comparison_output")
    output_dir.mkdir(exist_ok=True)
    
    # Configure error logging to file
    file_handler = logging.FileHandler("comparison_errors.log", mode='w')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)

    # 1. Setup Models
    models_to_test = [
        {"name": "gemini-2.5-flash-lite", "description": "Ultra-light / Preview"},
        {"name": "gemini-2.5-flash", "description": "Standard Balanced"}
    ]
    
    # 2. Prepare Images
    print(f"📸 Converting PDF pages {pages_to_test} to images...")
    images = convert_from_path(
        pdf_path, 
        first_page=min(pages_to_test), 
        last_page=max(pages_to_test), 
        dpi=250
    )
    
    results = []
    
    # 3. Benchmark Loop
    for model_info in models_to_test:
        model_id = model_info["name"]
        print(f"\n🚀 Benchmarking Model: {model_id} ({model_info['description']})")
        print("-" * 60)
        
        config = ExtractionConfig(
            primary_model=model_id,
            enable_auto_upgrade=False, # Force single model usage
            use_vertex_ai=True,
            location="us-central1"
        )
        
        extractor = VisionExtractor(config)
        
        for i, img in enumerate(images):
            page_num = pages_to_test[i]
            print(f"Processing Page {page_num}...")
            
            start_time = time.time()
            try:
                # Direct extraction call
                extracted_data = extractor.extract_page(img, page_num=page_num)
                duration = time.time() - start_time
                
                # Save content for comparison
                content_text = f"--- Model: {model_id} | Page: {page_num} ---\n"
                for block in extracted_data.content_blocks:
                    content_text += f"\n[{block.content_type.value.upper()}]\n"
                    
                    # Handle verse blocks
                    if block.verse_data:
                        content_text += f"Sanskrit: {block.verse_data.sanskrit_text}\n"
                        content_text += f"Eng: {block.verse_data.translation}\n"
                    # Handle table blocks
                    elif block.table_data:
                        if block.table_data.markdown:
                            content_text += f"{block.table_data.markdown}\n"
                        elif block.table_data.rows:
                            # Fallback: print rows if markdown not available
                            for row in block.table_data.rows:
                                content_text += f"{' | '.join(str(cell) for cell in row)}\n"
                    # Handle regular text blocks
                    else:
                        content_text += f"{block.text}\n"
                
                # Write to file
                safe_model_name = model_id.replace("models/", "").replace("gemini-", "")
                with open(output_dir / f"p{page_num}_{safe_model_name}.txt", "w", encoding="utf-8") as f:
                    f.write(content_text)
                
                # Collect metrics
                results.append({
                    "Model": model_id,
                    "Page": page_num,
                    "Status": "Success",
                    "Time (s)": round(duration, 2),
                    "Confidence": extracted_data.extraction_confidence,
                    "Blocks": len(extracted_data.content_blocks)
                })
                
            except Exception as e:
                logger.error(f"Failed page {page_num} with {model_id}: {str(e)}", exc_info=True)
                print(f"❌ Failed page {page_num}: {str(e)}")
                results.append({
                    "Model": model_id, "Page": page_num, "Status": "Failed",
                    "Time (s)": 0, "Confidence": 0, "Blocks": 0
                })

    # 4. Generate Report
    df = pd.DataFrame(results)
    
    # Add Pass/Fail based on 90% threshold logic
    df["Pass (>=0.9)"] = df["Confidence"] >= 0.9
    
    print("\n" + "="*80)
    print("📊 EXTRACTION COMPARISON SUMMARY")
    print("="*80)
    
    summary = df.groupby("Model").agg({
        "Time (s)": "mean",
        "Confidence": "mean",
        "Blocks": "mean",
        "Pass (>=0.9)": "mean"  # This becomes the pass rate (0.0 to 1.0)
    }).round(3)
    
    # Rename for clarity
    summary = summary.rename(columns={"Pass (>=0.9)": "Pass Rate"})
    
    print(tabulate(summary, headers='keys', tablefmt='psql'))
    
    # Calculate relative cost based on estimated rates (Verify current pricing)
    # Gemini 1.5 Flash: ~$0.075 / 1M input (approx)
    # Gemini 1.5 Pro:   ~$3.50  / 1M input (approx)
    # Note: 2.5 pricing may vary, using conservative estimates for comparison
    print("\n💰 COST ANALYSIS (Relative Estimation)")
    print("-" * 40)
    # Assuming standard page is ~1.5k tokens (image + text)
    tokens_per_1k_pages = 1000 * 1500 
    
    # Estimated Input Cost per 1M tokens
    cost_lite = 0.075  # Placeholder for Flash-Lite (often cheaper or same as Flash)
    cost_flash = 0.10  # Placeholder for Flash
    
    print(f"Est. Tokens per 1k pages : {tokens_per_1k_pages / 1_000_000:.2f} Million")
    print(f"Scenario: If Lite is ${cost_lite} and Flash is ${cost_flash} per 1M tokens:")
    
    est_lite = (tokens_per_1k_pages / 1_000_000) * cost_lite
    est_flash = (tokens_per_1k_pages / 1_000_000) * cost_flash
    
    print(f"Gemini Flash-Lite Cost   : ~${round(est_lite, 3)}")
    print(f"Gemini Flash Cost        : ~${round(est_flash, 3)}")

    # Save to CSV
    output_file = "model_comparison_results.csv"
    df.to_csv(output_file, index=False)
    print(f"\n✅ Detailed results saved to: {output_file}")

if __name__ == "__main__":
    test_pdf = "data/raw/Brihat Parasara Hora Sastra Vol 1 by Maharishi Parashara.pdf"
    pages = [25, 26, 27] # Test a small sample
    
    if not Path(test_pdf).exists():
        print(f"❌ PDF not found at {test_pdf}")
    else:
        run_comparison(test_pdf, pages)
