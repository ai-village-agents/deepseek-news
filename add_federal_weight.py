import major_news_config

# Check if federal_register is in weights
config = major_news_config.MAJOR_NEWS_CONFIG
if "federal_register" in config.get("weights", {}):
    print("federal_register already in weights:", config["weights"]["federal_register"])
else:
    print("federal_register NOT in weights")
    print("Current weights keys:", list(config.get("weights", {}).keys()))
