def on_pre_build(config):
    import subprocess
    subprocess.run(["python", "scripts/gen_api_docs.py"], check=True)
