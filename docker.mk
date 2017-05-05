.PHONY: docker.build docker.test docker.pkg

# Define OPENEDX_RELEASE in the environment to build something other than master.
OPENEDX_RELEASE ?= master
ifneq ($(OPENEDX_RELEASE),master)
	IMAGE_PREFIX := $(patsubst open-release/%.master,%/,$(OPENEDX_RELEASE))
endif

SHARD=0
SHARDS=1

dockerfiles:=$(shell ls docker/build/*/Dockerfile)
all_images:=$(patsubst docker/build/%/Dockerfile,%,$(dockerfiles))

# Used in the test.mk file as well.
images:=$(if $(TRAVIS_COMMIT_RANGE),$(shell git diff --name-only $(TRAVIS_COMMIT_RANGE) | python util/parsefiles.py),$(all_images))

docker_build=docker.build.
docker_test=docker.test.
docker_pkg=docker.pkg.
docker_push=docker.push.

help: docker.help

docker.help:
	@echo '    Docker:'
	@echo '        $$image: any dockerhub image'
	@echo '        $$container: any container defined in docker/build/$$container/Dockerfile'
	@echo ''
	@echo '        $(docker_pull)$$image        pull $$image from dockerhub'
	@echo ''
	@echo '        $(docker_build)$$container   build $$container'
	@echo '        $(docker_test)$$container    test that $$container will build'
	@echo '        $(docker_pkg)$$container     package $$container for a push to dockerhub'
	@echo '        $(docker_push)$$container    push $$container to dockerhub '
	@echo ''
	@echo '        docker.build          build all defined docker containers (based on dockerhub base images)'
	@echo '        docker.test           test all defined docker containers'
	@echo '        docker.pkg            package all defined docker containers (using local base images)'
	@echo '        docker.push           push all defined docker containers'
	@echo ''

# N.B. / is used as a separator so that % will match the /
# in something like 'edxops/trusty-common:latest'
# Also, make can't handle ':' in filenames, so we instead '@'
# which means the same thing to docker
docker_pull=docker.pull/

build: docker.build

test: docker.test

pkg: docker.pkg

clean: docker.clean

docker.clean:
	rm -rf .build

docker.test.shard: $(foreach image,$(shell echo $(images) | python util/balancecontainers.py $(SHARDS) | awk 'NR%$(SHARDS)==$(SHARD)'),$(docker_test)$(image))

docker.build: $(foreach image,$(images),$(docker_build)$(image))
docker.test: $(foreach image,$(images),$(docker_test)$(image))
docker.pkg: $(foreach image,$(images),$(docker_pkg)$(image))
docker.push: $(foreach image,$(images),$(docker_push)$(image))

BUILD_ARGS = --build-arg OPENEDX_RELEASE=$(OPENEDX_RELEASE) --build-arg IMAGE_PREFIX=$(IMAGE_PREFIX)
BUILD_DIR = .build/$(IMAGE_PREFIX)

$(docker_pull)%:
	docker pull $(subst @,:,$*)

$(docker_build)%: docker/build/%/Dockerfile
	docker build $(BUILD_ARGS) -f $< .

$(docker_test)%: $(BUILD_DIR)%/Dockerfile.test
	docker build $(BUILD_ARGS) -t $(IMAGE_PREFIX)$*:test -f $< .

$(docker_pkg)%: $(BUILD_DIR)%/Dockerfile.pkg
	docker build $(BUILD_ARGS) -t $(IMAGE_PREFIX)$*:latest -f $< .

$(docker_push)%: $(docker_pkg)%
	docker tag $(IMAGE_PREFIX)$*:latest edxops/$(IMAGE_PREFIX)$*:latest
	docker push edxops/$(IMAGE_PREFIX)$*:latest

.SECONDARY: $(BUILD_DIR)%/Dockerfile.d $(BUILD_DIR)%/Dockerfile.test $(BUILD_DIR)%/Dockerfile.pkg

$(BUILD_DIR)%/Dockerfile.d: docker/build/%/Dockerfile Makefile
	@mkdir -p $(BUILD_DIR)$*
	$(eval FROM=$(shell grep "^\s*FROM" $< | sed -E "s/FROM //" | sed -E "s/\\\$${IMAGE_PREFIX}//" | sed -E "s/:/@/g"))
	$(eval EDXOPS_FROM=$(shell echo "$(FROM)" | sed -E "s#edxops/([^@]+)(@.*)?#\1#"))
	@echo "$(docker_build)$*: $(docker_pull)$(FROM)" > $@
	@if [ "$(EDXOPS_FROM)" != "$(FROM)" ]; then \
	echo "$(docker_test)$*: $(docker_test)$(EDXOPS_FROM:@%=)" >> $@; \
	echo "$(docker_pkg)$*: $(docker_pkg)$(EDXOPS_FROM:@%=)" >> $@; \
	else \
	echo "$(docker_test)$*: $(docker_pull)$(FROM)" >> $@; \
	echo "$(docker_pkg)$*: $(docker_pull)$(FROM)" >> $@; \
	fi

$(BUILD_DIR)%/Dockerfile.test: docker/build/%/Dockerfile Makefile
	@mkdir -p $(BUILD_DIR)$*
	@# perl p (print the line) n (loop over every line) e (exec the regex), like sed but cross platform
	@perl -pne "s#FROM edxops/([^:]+)(:\S*)?#FROM \1:test#" $< > $@

$(BUILD_DIR)%/Dockerfile.pkg: docker/build/%/Dockerfile Makefile
	@mkdir -p $(BUILD_DIR)$*
	@# perl p (print the line) n (loop over every line) e (exec the regex), like sed but cross platform
	@perl -pne "s#FROM edxops/([^:]+)(:\S*)?#FROM \1:test#" $< > $@

-include $(foreach image,$(images),$(BUILD_DIR)$(image)/Dockerfile.d)
