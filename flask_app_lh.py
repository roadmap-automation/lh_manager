from attr import asdict
from flask import Flask, render_template, request
from flask_restful import Resource, Api
from samplelist import lh_methods, SampleContainer, SampleStatus, example_sample_list, lh_method_fields, Sample
from layoutmap import racks
from bedlayout import LHBedLayout
from dataclasses import asdict
from copy import copy, deepcopy

app = Flask(__name__)
api = Api(app)

# ====== Define state variables: samples, layout =========

# TODO: Refactor so samples (which contains state) is imported from a separate state.py;
# this allows each module that will interact with samples to import the same object separately
# so state.samples becomes essentially a global variable

samples = SampleContainer()

for example_sample in example_sample_list:
    samples.addSample(example_sample)

layout = LHBedLayout(racks={})
for name, rack in racks.items():
    layout.add_rack_from_dict(name, rack)

class GetListofSampleLists(Resource):
    def get(self):
        sample_list = [sample.toSampleList(entry=True) for sample in samples.samples if sample.status==SampleStatus.ACTIVE]
        if len(sample_list):
            return {'sampleLists': sample_list}, 200
        else:
            return {}, 200

class GetSampleList(Resource):
    def get(self, sample_list_id):
        return {'sampleList': samples.getSample('id', sample_list_id, status=SampleStatus.ACTIVE).toSampleList()}, 200

class PutSampleListValidation(Resource):
    def post(self, sample_list_id):
        data = request.get_json(force=True)

        # check validation (SUCCESS or ERROR)
        validation = data['validation']['validationType']
        
        # TODO: Actual error handling flow
        assert validation == 'SUCCESS', f'Error in validation. Full message: ' + data['validation']['message']

        return {sample_list_id: validation}, 200

class PutSampleData(Resource):
    def post(self):
        data = request.get_json(force=True)

        # Get ID, method number, and method name from returned data
        sample_id = data['sampleData']['runData'][0]['sampleListID']
        method_number = int(data['sampleData']['runData'][0]['iteration']) - 1
        method_name = data['sampleData']['runData'][0]['methodName']

        # check that run was successful
        successful = False
        for notification in data['sampleData']['resultNotifications']['notifications'].values():
            if "completed successfully" in notification:
                successful = True
        
        if successful:
            # find relevant sample by ID
            sample = samples.getSample('id', sample_id)

            # double check that correct method is being referenced
            assert method_name == sample.methods[method_number].METHODNAME, f'Wrong method name {method_name} in result, expected {sample.methods[method_number].METHODNAME}, full output ' + data

            # mark method complete
            sample.methods_complete[method_number] = True

            # TODO: implement change of layout state as follows:
            #sample.methods[method_number].execute(layout)

            # if all methods complete, change status of sample to completed
            if all(sample.methods_complete):
                sample.status = SampleStatus.COMPLETED

        # TODO: ELSE: Throw error

        return {'data': data}, 200

class AddSample(Resource):
    """Adds a single-method sample to the sample list (testing only)"""
    def post(self):
        data = request.get_json(force=True)
        new_method = lh_methods[data['METHODNAME']](**data)
        new_sample = Sample(id=f'{samples.getMaxIndex("id") + 1}', name=data['SAMPLENAME'], description=data['SAMPLEDESCRIPTION'], methods=[new_method])
        samples.addSample(new_sample)

        # dry run (testing only)
        test_layout = deepcopy(layout)
        for method in new_sample.methods:
            method.execute(test_layout)

        return {'new sample': new_sample.toSampleList(), 'layout': asdict(test_layout)}, 200

class RunSample(Resource):
    """Runs a sample """
    # TODO: Use POST to change status; might be useful for pausing, stopping; as coded this is best as a PUT
    def get(self, sample_name):
        sample = samples.getSample('name', sample_name)
        if sample is not None:
            sample.status = SampleStatus.ACTIVE
            return {}, 200
        else:
            return {}, 404

class GetSamples(Resource):
    """Gets list of sample names, IDs, and status"""
    def get(self):

        sample_list = []
        for sample in samples.samples:
            sample_list.append(dict({
                'id': sample.id,
                'name': sample.name,
                'status': sample.status
            }))
        
        return {'samples': sample_list}, 200

# LH URIs
api.add_resource(GetListofSampleLists, '/LH/GetListofSampleLists')
api.add_resource(GetSampleList, '/LH/GetSampleList/<sample_list_id>')
api.add_resource(PutSampleData, '/LH/PutSampleData')
api.add_resource(PutSampleListValidation, '/LH/PutSampleListValidation/<sample_list_id>')

# Should these be LH endpoints, or NICE endpoints, or general API?
api.add_resource(RunSample, '/test/RunSample/<sample_name>')
api.add_resource(GetSamples, '/test/GetSamples/')
api.add_resource(AddSample, '/test/AddSample')

class GetLHMethods(Resource):
    def get(self):
        return lh_method_fields, 200

# GUI URIs
api.add_resource(GetLHMethods, '/GUI/GetLHMethods/')

@app.route('/')
def root():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=True)