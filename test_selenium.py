from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
import sys

# Aggiungi il path del progetto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_selenium():
    """Test Selenium con Chrome driver"""
    try:
        # Prova a usare chromedriver automaticamente (se in PATH)
        # Altrimenti specifica il percorso manualmente
        driver = webdriver.Chrome()
        
        print("✅ Chrome driver avviato correttamente")
        
        driver.get("https://www.youtube.com")
        print(f"✅ Pagina aperta: {driver.title}")
        
        # Test semplice: verifica che siamo su YouTube
        if "YouTube" in driver.title:
            print("✅ Siamo su YouTube!")
        
        driver.quit()
        print("✅ Driver chiuso correttamente")
        print("\n🎉 SELENIUM FUNZIONA! Pronto per il Giorno 1")
        return True
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        print("\nSoluzione:")
        print("1. Scarica ChromeDriver da: https://chromedriver.chromium.org/downloads")
        print("2. Metti il file chromedriver in una cartella del PATH")
        print("3. Oppure specifica il percorso: webdriver.Chrome(executable_path='/percorso/chromedriver')")
        return False

if __name__ == "__main__":
    success = test_selenium()
    sys.exit(0 if success else 1)
