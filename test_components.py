"""
Простой тест для проверки основных компонентов
"""
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Проверка импортов"""
    print("Testing imports...")
    
    try:
        from config import Settings
        print("✓ Config imported")
    except Exception as e:
        print(f"✗ Config import failed: {e}")
        return False
    
    try:
        from processors import AudioProcessor, WhisperTranscriber, SemanticProcessor
        print("✓ Processors imported")
    except Exception as e:
        print(f"✗ Processors import failed: {e}")
        return False
    
    try:
        from storage import FileManager
        print("✓ Storage imported")
    except Exception as e:
        print(f"✗ Storage import failed: {e}")
        return False
    
    try:
        from bot import BotHandlers
        print("✓ Bot handlers imported")
    except Exception as e:
        print(f"✗ Bot handlers import failed: {e}")
        return False
    
    return True


def test_settings():
    """Проверка настроек"""
    print("\nTesting settings...")
    
    try:
        from config import Settings
        
        # Проверка критичных настроек
        if not Settings.TELEGRAM_BOT_TOKEN:
            print("⚠ TELEGRAM_BOT_TOKEN not set")
        else:
            print("✓ Telegram token configured")
        
        if Settings.ALLOWED_USER_ID == 0:
            print("⚠ ALLOWED_USER_ID not set")
        else:
            print(f"✓ Allowed user ID: {Settings.ALLOWED_USER_ID}")
        
        print(f"✓ Notes directory: {Settings.NOTES_DIR}")
        print(f"✓ Categories: {', '.join(Settings.CATEGORIES)}")
        
        return True
        
    except Exception as e:
        print(f"✗ Settings test failed: {e}")
        return False


def test_file_manager():
    """Проверка файлового менеджера"""
    print("\nTesting file manager...")
    
    try:
        from storage import FileManager
        
        fm = FileManager()
        
        # Проверка создания директорий
        for category in ['идеи', 'жизнь', 'работа', 'инбокс']:
            if not (fm.notes_dir / category).exists():
                print(f"✗ Category directory missing: {category}")
                return False
        
        print("✓ All category directories exist")
        
        # Статистика
        stats = fm.get_stats()
        print(f"✓ Current notes: {stats['total']}")
        
        return True
        
    except Exception as e:
        print(f"✗ File manager test failed: {e}")
        return False


def test_audio_processor():
    """Проверка аудио процессора"""
    print("\nTesting audio processor...")
    
    try:
        from processors import AudioProcessor
        
        ap = AudioProcessor()
        print("✓ Audio processor initialized")
        
        # Проверка FFmpeg
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        if result.returncode == 0:
            print("✓ FFmpeg available")
        else:
            print("⚠ FFmpeg check failed")
        
        return True
        
    except FileNotFoundError:
        print("✗ FFmpeg not found")
        return False
    except Exception as e:
        print(f"✗ Audio processor test failed: {e}")
        return False


def main():
    """Запуск всех тестов"""
    print("=" * 50)
    print("AI Notes Bot - Component Tests")
    print("=" * 50)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Settings", test_settings()))
    results.append(("File Manager", test_file_manager()))
    results.append(("Audio Processor", test_audio_processor()))
    
    print("\n" + "=" * 50)
    print("Test Results:")
    print("=" * 50)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:20} {status}")
    
    print("=" * 50)
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
