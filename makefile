
docker-build :
	docker build -f Dockerfile -t run_pahole:latest .

# the mount path of the following example should be modified to your needs.
docker-attach :
	docker run -it --rm --mount type=bind,source="$(CURDIR)",target=/project run_pahole:latest /bin/bash
