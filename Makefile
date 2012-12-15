run:
	cd local-runner && ./local-runner-sync.sh
	sleep 2
	CODETANKS_DEBUG_SCREEN=1 python3 Runner.py

prepare: clean
	wget -O python3-cgdk.zip "http://russianaicup.ru/s/1353065883304/assets/cgdks/python3-cgdk.zip?rnd"
	unzip python3-cgdk.zip
	mv python3-cgdk/model python3-cgdk/RemoteProcessClient.py python3-cgdk/Runner.py .
	rm -r python3-cgdk*

	wget -O local-runner.zip "http://russianaicup.ru/s/1353255447252/assets/local-runner/local-runner.zip?rnd"
	mkdir local-runner
	cd local-runner && unzip ../local-runner.zip
	chmod a+x ./local-runner/*.sh
	rm local-runner.zip

build:
	zip -9 build.zip *.py -x RemoteProcessClient.py -x Runner.py

clean:
	rm -rf local-runner model __pycache__ build.zip RemoteProcessClient.py Runner.py
