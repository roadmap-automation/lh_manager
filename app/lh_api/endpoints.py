from flask import make_response, Response, request
from lh_api import lh_blueprint
from state.state import samples
from liquid_handler.samplelist import SampleStatus

@lh_blueprint.route('/LH/GetListofSampleLists/', methods=['GET'])
def GetListofSampleLists() -> Response:
    sample_list = [sample.toSampleList(entry=True) for sample in samples.samples if sample.status==SampleStatus.ACTIVE]

    return make_response({'sampleLists': sample_list}, 200)

@lh_blueprint.route('/LH/GetSampleList/<sample_list_id>', methods=['GET'])
def GetSampleList(sample_list_id) -> Response:
    
    return make_response({'sampleList': samples.getSamplebyID(int(sample_list_id), status=SampleStatus.ACTIVE).toSampleList()}, 200)

@lh_blueprint.route('/LH/PutSampleListValidation/<sample_list_id>', methods=['POST'])
def PutSampleListValidation(sample_list_id):
    data = request.get_json(force=True)

    # check validation (SUCCESS or ERROR)
    validation = data['validation']['validationType']
    
    # TODO: Actual error handling flow
    assert validation == 'SUCCESS', f'Error in validation. Full message: ' + data['validation']['message']

    return make_response({sample_list_id: validation}, 200)

@lh_blueprint.route('/LH/PutSampleData/', methods=['POST'])
def PutSampleData():
    data = request.get_json(force=True)

    # Get ID, method number, and method name from returned data
    sample_id = int(data['sampleData']['runData'][0]['sampleListID'])
    method_number = int(data['sampleData']['runData'][0]['iteration']) - 1
    method_name = data['sampleData']['runData'][0]['methodName']

    # check that run was successful
    if any([('completed successfully' in notification) for notification in data['sampleData']['resultNotifications']['notifications'].values()]):
        # find relevant sample by ID
        sample = samples.getSamplebyID(sample_id)

        # double check that correct method is being referenced
        assert method_name == sample.methods[method_number].method_name, f'Wrong method name {method_name} in result, expected {sample.methods[method_number].method_name}, full output ' + data

        # mark method complete
        sample.methods_complete[method_number] = True

        # TODO: implement change of layout state as follows:
        #sample.methods[method_number].execute(layout)

        # if all methods complete, change status of sample to completed
        if all(sample.methods_complete):
            sample.status = SampleStatus.COMPLETED

    # TODO: ELSE: Throw error

    return make_response({'data': data}, 200)