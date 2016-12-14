# To build this Dockerfile:
#
# From the root of configuration:
#
# docker build -f docker/build/edxapp/Dockerfile . -t edxops/edxapp:devstack
#
# This allows the dockerfile to update /edx/app/edx_ansible/edx_ansible
# with the currently checked-out configuration repo.


# TODO Revert this once we are done testing. Having this greatly cuts down on
# build time since we don't have to checkout the repo or install requirements from scratch.
FROM clintonb/edxapp:devstack
#FROM edxops/precise-common:latest
MAINTAINER edxops

USER root
ADD . /edx/app/edx_ansible/edx_ansible
WORKDIR /edx/app/edx_ansible/edx_ansible/docker/plays
COPY docker/build/edxapp/ansible_overrides.yml /
#RUN apt-get update

RUN /edx/app/edx_ansible/venvs/edx_ansible/bin/ansible-playbook edxapp.yml \
    -c local -i '127.0.0.1,' \
    -t "install,assets,devstack,install:base,install:configuration,install:app-requirements,install:code" \
    --extra-vars="@/ansible_overrides.yml" \
    --extra-vars="EDXAPP_PYTHON_SANDBOX=false"


CMD ["/edx/app/supervisor/venvs/supervisor/bin/supervisord", "-n", "--configuration", "/edx/app/supervisor/supervisord.conf"]
EXPOSE 18000 18010
