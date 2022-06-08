
ROOT_DIR ?= $(CURDIR)/../..
ARGS ?=

docker-build :
	docker build -f Dockerfile -t run_pahole:latest .

# demo for launching the image, the mount path of the following example should be modified to your needs
docker-attach :
	docker run -it --rm --mount type=bind,source="$(ROOT_DIR)",target=/project run_pahole:latest /bin/bash

# demo on how to run the docker image with a custom argument (path to your .json file within the mount)
docker-run :
	docker run --rm --mount type=bind,source="$(ROOT_DIR)",target=/project run_pahole:latest $(ARGS)
